#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terax 中文版 · 构建后 dist 汉化补丁。

在 `vite build` 之后、Tauri 打包之前运行,对前端产物做**精确全等**的字符串替换:

- 仅当「整个字符串字面量」的内容与翻译键完全一致时才替换,不做任何子串替换;
  标识符、API 路径、配置键、动态拼接一概不会被命中;
- 扫描对象为 vite 产物(dist)中的 .js/.mjs/.html/.css;JSX 文本在编译产物中
  已是普通字符串字面量,因此能覆盖到源码级正则方案(方案D原文)抓不到的部分;
- 翻译表由人工维护(见 i18n/translations.json),只收录确定的 UI 文案,保守优先;
- 幂等:替换结果为中文,不会再次命中英文键,重复运行无副作用;
- 替换统计写入 --report 指定的 JSON(必须位于 dist 之外,否则会被打进应用包)。

用法(通常由 apply_i18n.py 写入 tauri.conf.json 的 beforeBuildCommand 自动调用):
  python patch_dist.py --dist <dist目录> --map <translations.json> --report <report.json>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 ANSI 代码页(如 cp1252/cp936),直接 print 中文会 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError, ValueError):
            pass


_force_utf8_stdio()

# 字符串字面量(双引号/单引号/反引号)。组1=双引号内容,组2=单引号内容,组3=反引号内容。
# 注意:刻意不匹配跨行双/单引号字符串,产物中最小化输出几乎不产生这类形态。
LITERAL_RE = re.compile(
    r'"((?:[^"\\\n]|\\.)*)"'
    r"|'((?:[^'\\\n]|\\.)*)'"
    r'|`((?:[^`\\]|\\.)*)`'
)

# HTML 中允许替换的展示性属性(白名单,避免误碰 name= 之类数据属性)
HTML_ATTRS = ('placeholder', 'title', 'aria-label', 'alt')

TARGET_SUFFIXES = {'.js', '.mjs', '.html', '.css'}
MAX_FILE_BYTES = 100 * 1024 * 1024


def patch_js_css(text: str, mapping: dict[str, str]) -> tuple[str, dict[str, int]]:
    """替换 JS/CSS 中的字符串字面量(整串全等)。"""
    hits: dict[str, int] = {}

    def repl(m: re.Match) -> str:
        if m.group(1) is not None:
            quote, raw = '"', m.group(1)
        elif m.group(2) is not None:
            quote, raw = "'", m.group(2)
        else:
            quote, raw = '`', m.group(3)
        # 反引号模板串:含插值或转义的一律跳过,只替换纯静态串
        if quote == '`' and ('${' in raw or '\\' in raw):
            return m.group(0)
        cn = mapping.get(raw)
        if cn is None:
            return m.group(0)
        hits[raw] = hits.get(raw, 0) + 1
        return quote + cn + quote

    return LITERAL_RE.sub(repl, text), hits


def patch_html(text: str, mapping: dict[str, str]) -> tuple[str, dict[str, int]]:
    """替换 HTML 文本节点(>KEY<)与白名单展示属性(="KEY"),并把 lang 改为 zh-CN。

    属性替换按白名单逐属性正则匹配,避免整体 replace 误伤 name= 等数据属性。
    """
    hits: dict[str, int] = {}
    # 长键优先,避免短键包裹形式意外命中(实际上 >KEY< 定界已隔离,这里再保险)
    for en in sorted(mapping, key=len, reverse=True):
        cn = mapping[en]
        old = f'>{en}<'
        count = text.count(old)
        if count:
            text = text.replace(old, f'>{cn}<')
            hits[en] = hits.get(en, 0) + count
        attr_re = re.compile(
            r'(?<![\w-])(placeholder|title|aria-label|alt)="(' + re.escape(en) + r')"')
        text, n = attr_re.subn(lambda m: f'{m.group(1)}="{cn}"', text)
        if n:
            hits[en] = hits.get(en, 0) + n
    text, n = re.subn(r'(<html[^>]*?\blang=")en(")', r'\1zh-CN\2', text)
    if n:
        hits['(html lang)'] = n
    return text, hits


def iter_targets(dist: Path):
    for p in sorted(dist.rglob('*')):
        if p.is_file() and p.suffix.lower() in TARGET_SUFFIXES and p.stat().st_size <= MAX_FILE_BYTES:
            yield p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description='Terax 中文版 dist 汉化补丁')
    ap.add_argument('--dist', required=True, help='vite 产物目录(如 <上游>/dist)')
    ap.add_argument('--map', required=True, help='翻译表 JSON(扁平 {英文: 中文})')
    ap.add_argument('--report', required=True, help='统计报告输出路径(须在 dist 之外)')
    ap.add_argument('--min-replacements', type=int, default=1,
                    help='最少替换次数,低于该值视为异常并以非零码退出(防静默英文版)')
    args = ap.parse_args(argv)

    dist = Path(args.dist)
    if not dist.is_dir():
        print(f'[patch-dist] 错误: dist 目录不存在: {dist}', file=sys.stderr)
        return 2

    try:
        mapping = json.loads(Path(args.map).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'[patch-dist] 错误: 翻译表读取失败: {exc}', file=sys.stderr)
        return 2
    if not isinstance(mapping, dict) or not mapping:
        print('[patch-dist] 错误: 翻译表必须是非空扁平 {英文: 中文} 映射', file=sys.stderr)
        return 2
    if any(not isinstance(v, str) or not v.strip() for v in mapping.values()):
        print('[patch-dist] 错误: 翻译表存在非字符串或空白的中文值', file=sys.stderr)
        return 2

    files_report: dict[str, dict[str, int]] = {}
    patched = 0
    scanned = 0
    for path in iter_targets(dist):
        scanned += 1
        # newline='' 保持原始换行符:Windows 上默认文本模式会把 \n 写成 \r\n,破坏产物
        with open(path, 'r', encoding='utf-8', errors='strict', newline='') as fh:
            text = fh.read()
        if path.suffix.lower() == '.html':
            new_text, hits = patch_html(text, mapping)
        else:
            new_text, hits = patch_js_css(text, mapping)
        if hits:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(new_text)
            patched += 1
            files_report[str(path.relative_to(dist).as_posix())] = hits

    total = sum(sum(c.values()) for c in files_report.values())
    keys_used = {k for c in files_report.values() for k in c}
    unused = sorted(k for k in mapping if k not in keys_used)
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'dist': str(dist),
        'keys_total': len(mapping),
        'summary': {
            'replacements': total,
            'files_patched': patched,
            'files_scanned': scanned,
            'keys_used': len(keys_used),
        },
        'files': files_report,
        'unused_keys': unused,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print(f"[patch-dist] 扫描 {scanned} 个文件,替换 {total} 处,命中 {patched} 个文件,"
          f"使用 {len(keys_used)}/{len(mapping)} 个词条")
    if total < args.min_replacements:
        print(f'[patch-dist] 错误: 替换次数({total})低于下限({args.min_replacements}),'
              '疑似上游界面结构大改或翻译表失效,拒绝产出英文版', file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main())
