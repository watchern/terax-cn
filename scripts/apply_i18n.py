#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把中文汉化与品牌合规补丁挂载到上游 Terax 源码树(CI 构建的前置步骤)。

全部改动集中在上游克隆内的少数配置文件,源码零修改:

1. 校验上游结构,缺失即报错退出,绝不静默产出英文版;
2. build.beforeBuildCommand 追加 patch_dist.mjs 调用(Node+acorn,构建后精确替换);
3. bundle.createUpdaterArtifacts 置为 false(无官方签名私钥);
4. 品牌合规(默认开启,--no-rename 关闭):
   - productName / 主窗口标题 → --app-name(默认 Teal-CN,不含原商标);
   - identifier → --identifier(默认 io.github.watchern.teraxcn,替换 crynta 标识);
   - 图标全套替换(assets/brand/ 按 tauri.conf 的 icon 清单逐项覆盖)+ public/logo.png;
   - fileAssociations 名称去商标;publisher/copyright 改为分发者并保留原版权归属;
   - bundle.resources 增加上游 LICENSE 副本(Apache-2.0 第 4 条:随分发提供许可文本);
   - NSIS 安装器语言追加简体中文;
   - longDescription 改写为「非官方中文分发」声明;
   - 翻译表解析副本注入 "Terax"→应用名、"app.crynta.terax"→新标识符(界面残留品牌点);
5. 打印变更摘要;在 GitHub Actions 中同步写入 $GITHUB_STEP_SUMMARY。

用法:
  python apply_i18n.py --upstream <上游源码目录> --map i18n/translations.json \
      --report <报告输出路径(仓库根/dist 之外)>
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    """Windows 控制台默认 ANSI 代码页(如 cp1252/cp936),直接 print 中文会 UnicodeEncodeError。"""
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
    ap = argparse.ArgumentParser(description='挂载 Terax 中文汉化与品牌合规补丁')
    ap.add_argument('--upstream', required=True, help='上游源码根目录')
    ap.add_argument('--map', required=True, help='翻译表 JSON 路径(扁平 {英文: 中文})')
    ap.add_argument('--report', required=True, help='dist 汉化统计报告输出路径(必须在 dist 之外)')
    ap.add_argument('--patch-script', default=None,
                    help='patch_dist.mjs 路径,默认取本脚本同目录')
    ap.add_argument('--app-name', default='Terax-CN', help='改名后的应用名')
    ap.add_argument('--identifier', default='io.github.watchern.teraxcn', help='新的应用标识符')
    ap.add_argument('--no-rename', action='store_true', help='跳过改名/换标(仅汉化)')
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
    brand_dir = Path(__file__).resolve().parent.parent / 'assets' / 'brand'
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

    # ---- 1. 构建链挂载(dist 精确替换) ----
    bbc = build['beforeBuildCommand']
    if 'patch_dist.mjs' in bbc:
        print('[apply-i18n] beforeBuildCommand 已挂载补丁,跳过(幂等)')
    else:
        # Tauri 在 Windows 下执行 before* 命令时引号不会被 shell 剥离(实测原样进 argv),
        # 因此拼接的命令绝不能带引号;GH runner 路径无空格,可直接裸写,含空格路径提前拦下。
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

    # ---- 2. 品牌合规:改名、换标、归属 ----
    if not args.no_rename:
        app_name = args.app_name
        old_name = conf.get('productName')
        if old_name and old_name != app_name:
            conf['productName'] = app_name
            changes.append(('productName', old_name, app_name))
        windows = (conf.get('app') or {}).get('windows')
        if isinstance(windows, list) and windows and isinstance(windows[0], dict):
            old_title = windows[0].get('title')
            if old_title and old_title != app_name:
                windows[0]['title'] = app_name
                changes.append(('app.windows[0].title', old_title, app_name))

        old_id = conf.get('identifier')
        if old_id and old_id != args.identifier:
            conf['identifier'] = args.identifier
            changes.append(('identifier', old_id, args.identifier))

        # 图标全套替换:按 tauri.conf 的 icon 清单逐项覆盖
        icon_srcs = {'32x32.png', '128x128.png', '128x128@2x.png', 'icon.ico', 'icon.icns'}
        icons = bundle.get('icon')
        if not isinstance(icons, list) or not icons:
            fail('tauri.conf.json 缺少 bundle.icon 清单,无法替换图标')
        for icon_rel in icons:
            name = Path(icon_rel).name
            src = brand_dir / name
            if name not in icon_srcs or not src.is_file():
                fail(f'图标清单出现未备料的文件名 {icon_rel}(brand 目录缺 {name}),请更新 assets/brand')
            dst = conf_path.parent / icon_rel
            shutil.copyfile(src, dst)
        changes.append(('bundle.icon(全部替换)', 'Terax 官方图标', f'{app_name} 图标({len(icons)} 个文件)'))

        # 网页 favicon(设置页与主窗口标签页图标)
        logo_src = brand_dir / 'logo.png'
        logo_dst = upstream / 'public' / 'logo.png'
        if logo_dst.parent.is_dir():
            shutil.copyfile(logo_src, logo_dst)
            changes.append(('public/logo.png(favicon)', 'Terax 官方图标', f'{app_name} 图标'))
        else:
            print('[apply-i18n] 警告: 未找到 public/logo.png,跳过 favicon 替换')

        # 文件关联名称去商标
        associations = bundle.get('fileAssociations')
        if isinstance(associations, list) and associations and isinstance(associations[0], dict):
            old_fa = associations[0].get('name')
            if old_fa and 'Terax' in old_fa:
                associations[0]['name'] = f'{app_name} Document'
                changes.append(('bundle.fileAssociations[0].name', old_fa,
                                associations[0]['name']))

        # 发布者/版权:分发者署名 + 保留原代码版权归属(Apache-2.0 第 4 条)
        if bundle.get('publisher') is not None:
            old_pub = bundle['publisher']
            bundle['publisher'] = 'watchern'
            changes.append(('bundle.publisher', old_pub, 'watchern'))
        if bundle.get('copyright') is not None:
            old_cp = bundle['copyright']
            bundle['copyright'] = ('Original code Copyright Crynta (Apache-2.0). '
                                   f'Unofficial Chinese distribution by watchern ({app_name}).')
            changes.append(('bundle.copyright', old_cp, bundle['copyright']))

        # 随分发附带上游 LICENSE 文本(Apache-2.0 第 4 条 a/c)
        resources = bundle.get('resources')
        if isinstance(resources, dict):
            license_key = '../LICENSE'
            license_val = 'licenses/terax-apache-2.0.txt'
            if resources.get(license_key) != license_val:
                resources[license_key] = license_val
                changes.append(('bundle.resources["../LICENSE"]', '(缺省)', license_val))
            if not (upstream / 'LICENSE').is_file():
                fail(f'上游缺少 LICENSE 文件({upstream / "LICENSE"}),无法履行 Apache-2.0 附带义务')

        # NSIS 安装器追加简体中文
        nsis = ((bundle.get('windows') or {}).get('nsis') or {})
        langs = nsis.get('languages')
        if isinstance(langs, list) and 'SimpChinese' not in langs:
            langs.append('SimpChinese')
            changes.append(('bundle.windows.nsis.languages', str(langs[:-1]), str(langs)))

        # 包描述改为「非官方中文分发」声明(描述性提及上游,属正当引用)
        if bundle.get('longDescription') is not None:
            old_ld = bundle['longDescription']
            bundle['longDescription'] = (
                'Unofficial Chinese-localized community distribution of Terax, the open-source '
                'AI-native terminal emulator (Apache-2.0). Not affiliated with Crynta. '
                '界面已全面汉化,基于上游原版构建。')
            changes.append(('bundle.longDescription', old_ld, '(非官方中文分发声明)'))

        # 翻译表解析副本:注入界面残留品牌点的替换键
        resolved = dict(mapping)
        resolved['Terax'] = app_name
        resolved['app.crynta.terax'] = args.identifier
        resolved_path = report_path.parent / 'translations.resolved.json'
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved_path, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(resolved, fh, ensure_ascii=False, indent=2)
            fh.write('\n')

    conf_path.write_text(json.dumps(conf, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
                         newline='\n')

    print(f"[apply-i18n] 上游版本: {pkg.get('version', '?')}  包管理器: {pkg.get('packageManager', '?')}")
    print(f"[apply-i18n] 前端产物目录: {dist_abs}")
    for key, old, new in changes:
        print(f'[apply-i18n] 已修改 {key}')
    if not changes:
        print('[apply-i18n] 无需修改(可能已挂载)')

    gh_summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if gh_summary:
        with open(gh_summary, 'a', encoding='utf-8', newline='\n') as f:
            f.write('\n### 汉化与品牌合规补丁\n\n| 配置项 | 原值 | 新值 |\n|---|---|---|\n')
            for key, old, new in changes:
                f.write(f'| `{key}` | `{old}` | `{new}` |\n')
            f.write(f'\n词条总数:{len(mapping) if args.no_rename else len(mapping) + 2},'
                    f'前端产物目录:`{dist_abs}`\n')

    return 0


if __name__ == '__main__':
    sys.exit(main())
