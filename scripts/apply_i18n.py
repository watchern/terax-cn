#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把中文汉化补丁挂载到上游 Terax 源码树(CI 构建的前置步骤)。

全部改动集中在 src-tauri/tauri.conf.json 一个文件,上游源码零修改:

1. 校验上游结构(package.json / tauri.conf.json / 翻译表 / 补丁脚本),缺失即报错退出,
   绝不静默产出英文版;
2. build.beforeBuildCommand 追加 patch_dist.mjs 调用 —— 在 vite build 之后、Tauri 打包之前
   由 Node+acorn 对 dist 产物做精确全等替换(唯一构建链侵入点,自动幂等);
3. bundle.createUpdaterArtifacts 置为 false —— 本仓库没有官方 TAURI_SIGNING_PRIVATE_KEY,
   保留该开关 tauri build 会直接失败;
4. (默认开启,--no-rename 关闭)productName 与主窗口标题改为 "Terax-CN",
   使中文版与官方版可并存安装、互不覆盖;
5. 打印变更摘要;在 GitHub Actions 中同步写入 $GITHUB_STEP_SUMMARY。

用法:
  python apply_i18n.py --upstream <上游源码目录> --map i18n/translations.json \
      --report <报告输出路径(仓库根/dist 之外)>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 ANSI 代码页(如 cp1252/cp936),直接 print 中文会 UnicodeEncodeError。

    启动时把标准流重配为 UTF-8;errors='replace' 保证任何情况下日志都不会再炸。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, OSError, ValueError):
            pass


_force_utf8_stdio()


def fail(msg: str) -> 'NoReturn':  # type: ignore[valid-type]
    print(f'[apply-i18n] 错误: {msg}', file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description='挂载 Terax 中文汉化补丁')
    ap.add_argument('--upstream', required=True, help='上游源码根目录')
    ap.add_argument('--map', required=True, help='翻译表 JSON 路径(扁平 {英文: 中文})')
    ap.add_argument('--report', required=True, help='dist 汉化统计报告输出路径(必须在 dist 之外)')
    ap.add_argument('--patch-script', default=None,
                    help='patch_dist.py 路径,默认取本脚本同目录')
    ap.add_argument('--app-name', default='Terax-CN', help='改名后的应用名')
    ap.add_argument('--no-rename', action='store_true', help='不改 productName/窗口标题')
    args = ap.parse_args()

    upstream = Path(args.upstream).resolve()
    conf_path = upstream / 'src-tauri' / 'tauri.conf.json'
    pkg_path = upstream / 'package.json'
    if not conf_path.is_file():
        fail(f'未找到 {conf_path} —— 上游结构可能已变化,请人工核对后再调整本脚本')
    if not pkg_path.is_file():
        fail(f'未找到 {pkg_path} —— 上游结构可能已变化')

    patch_script = (Path(args.patch_script).resolve() if args.patch_script
                    else Path(__file__).resolve().parent / 'patch_dist.mjs')
    map_path = Path(args.map).resolve()
    report_path = Path(args.report).resolve()
    if not patch_script.is_file():
        fail(f'未找到补丁脚本 {patch_script}')
    if not map_path.is_file():
        fail(f'未找到翻译表 {map_path}')

    try:
        pkg = json.loads(pkg_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'package.json 解析失败: {exc}')
    try:
        mapping = json.loads(map_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'翻译表解析失败: {exc}')
    if not isinstance(mapping, dict) or not mapping:
        fail('翻译表必须是 {英文: 中文} 的非空扁平映射')
    bad = [k for k, v in mapping.items() if not isinstance(v, str) or not v.strip()]
    if bad:
        fail(f'翻译表存在非字符串或空白的中文值(前 5 个): {bad[:5]}')

    try:
        conf = json.loads(conf_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'tauri.conf.json 解析失败: {exc}')

    build = conf.get('build')
    if not isinstance(build, dict) or not build.get('beforeBuildCommand'):
        fail('tauri.conf.json 缺少 build.beforeBuildCommand,无法挂载补丁')
    frontend_dist = build.get('frontendDist')
    if not frontend_dist:
        fail('tauri.conf.json 缺少 build.frontendDist')
    dist_abs = (conf_path.parent / frontend_dist).resolve()  # frontendDist 相对 src-tauri 目录

    changes: list[tuple[str, str, str]] = []

    bbc = build['beforeBuildCommand']
    if 'patch_dist.mjs' in bbc:
        print('[apply-i18n] beforeBuildCommand 已挂载补丁,跳过(幂等)')
    else:
        # Tauri 在 Windows 下执行 before* 命令时引号不会被 shell 剥离(实测原样进 argv),
        # 因此拼接的命令绝不能带引号;GH runner 路径无空格,可直接裸写,但含空格路径必须提前拦下。
        for label, p in (('补丁脚本', patch_script), ('dist', dist_abs),
                         ('翻译表', map_path), ('报告', report_path)):
            if ' ' in str(p):
                fail(f'{label}路径包含空格({p}):Tauri 在 Windows 下执行 beforeBuildCommand '
                     '时引号无法安全转义,请把本仓库与 runner 工作目录放在无空格路径下')
        cmd = (f' && node {patch_script.as_posix()}'
               f' --dist {dist_abs.as_posix()}'
               f' --map {map_path.as_posix()}'
               f' --report {report_path.as_posix()}'
               f' --min-replacements 1')
        build['beforeBuildCommand'] = bbc + cmd
        changes.append(('build.beforeBuildCommand', bbc, build['beforeBuildCommand']))

    bundle = conf.get('bundle')
    if not isinstance(bundle, dict):
        fail('tauri.conf.json 缺少 bundle 配置')
    if bundle.get('createUpdaterArtifacts') is True:
        bundle['createUpdaterArtifacts'] = False
        changes.append(('bundle.createUpdaterArtifacts', 'true',
                        'false(本仓库无官方签名私钥,保留会导致 tauri build 失败)'))

    if not args.no_rename:
        old_name = conf.get('productName')
        if old_name and old_name != args.app_name:
            conf['productName'] = args.app_name
            changes.append(('productName', old_name, args.app_name))
        windows = (conf.get('app') or {}).get('windows')
        if isinstance(windows, list) and windows and isinstance(windows[0], dict):
            old_title = windows[0].get('title')
            if old_title and old_title != args.app_name:
                windows[0]['title'] = args.app_name
                changes.append(('app.windows[0].title', old_title, args.app_name))

    with open(conf_path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(conf, fh, ensure_ascii=False, indent=2)
        fh.write('\n')

    print(f"[apply-i18n] 上游版本: {pkg.get('version', '?')}  包管理器: {pkg.get('packageManager', '?')}")
    print(f"[apply-i18n] 前端产物目录: {dist_abs}")
    for key, old, new in changes:
        print(f'[apply-i18n] 已修改 {key}')
    if not changes:
        print('[apply-i18n] 无需修改(可能已挂载)')

    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a', encoding='utf-8') as f:
            f.write('\n### 汉化补丁挂载\n\n| 配置项 | 原值 | 新值 |\n|---|---|---|\n')
            for key, old, new in changes:
                f.write(f'| `{key}` | `{old}` | `{new}` |\n')
            f.write(f'\n词条总数:{len(mapping)},前端产物目录:`{dist_abs}`\n')

    return 0


if __name__ == '__main__':
    sys.exit(main())
