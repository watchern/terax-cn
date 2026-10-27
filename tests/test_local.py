#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""terax-cn 本地测试:验证 patch_dist.py 与 apply_i18n.py 的关键行为。

无需 pytest,直接运行:python tests/test_local.py
覆盖:
1. 字符串字面量精确全等替换(双/单/反引号),反引号含插值跳过;
2. 防误伤:子串、未加引号标识符、API 路径、协议值(不在翻译表)不被触碰;
3. HTML:文本节点、白名单属性、lang 属性;
4. 失败路径:dist 缺失、替换次数低于下限(防静默英文版)、非法翻译表;
5. apply_i18n:挂载 beforeBuildCommand、关闭 createUpdaterArtifacts、
   应用改名、幂等重跑、--no-rename、结构缺失报错、非法翻译表报错;
6. CRLF 保持:Windows 文本模式不改变换行符。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import patch_dist  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = '') -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ok  {name}')
    else:
        FAIL += 1
        print(f'FAIL  {name}  {detail}')


def make_dist(tmp: Path) -> Path:
    dist = tmp / 'dist'
    (dist / 'assets').mkdir(parents=True)
    # 模拟最小化产物:真键、陷阱混合
    bundle = (
        'const a="Cancel";const b=\'Close Anyway\';const c=`no matches`;'
        'const d=`run ${x}`;const e="Cancelled";\n'
        'const f="CancelNow";const g={Cancel:1,Close:2};invoke("pty_list_shells");listen("error",h);\n'
        'if(state==="done")log("running");const i="A process is running. Closing this tab will terminate it.";\n'
        'const j=\'Quit Terax?\';const k="Don\'t ask again about running processes";\n'
        'const l="Ask Terax anything   -   # for snippets and commands, @ for files";\n'
        'const m="Lines of history kept per terminal. Higher uses more RAM (~3 KB / line).";\n'
    )
    (dist / 'assets' / 'index-Ab12Cd34.js').write_text(bundle, encoding='utf-8', newline='')
    (dist / 'assets' / 'index-Ab12Cd34.js.map').write_text('{"version":3}', encoding='utf-8')
    html = (
        '<!doctype html>\n'
        '<html lang="en"><head><title>Terax</title></head>\n'
        '<body><div title="Close" name="Close">Unsaved Changes</div>\n'
        '<span aria-label="Close">x</span><button placeholder="Cancel">Go</button></body></html>'
    )
    (dist / 'index.html').write_text(html, encoding='utf-8', newline='')
    (dist / 'settings.html').write_text('<html lang="en"><body>ok</body></html>', encoding='utf-8')
    return dist


def map_path() -> Path:
    return REPO / 'i18n' / 'translations.json'


def test_patch_dist(tmp: Path) -> None:
    print('[patch_dist]')
    dist = make_dist(tmp)
    report_path = tmp / 'i18n-report.json'
    rc = patch_dist.main(['--dist', str(dist), '--map', str(map_path()),
                          '--report', str(report_path)])
    check('exit 0', rc == 0, f'rc={rc}')

    js = (dist / 'assets' / 'index-Ab12Cd34.js').read_text(encoding='utf-8')
    check('双引号替换', 'const a="取消"' in js)
    check('单引号替换', "const b='仍然关闭'" in js)
    check('反引号静态替换', 'const c=`无匹配`' in js)
    check('反引号含插值跳过', 'const d=`run ${x}`' in js)
    check('子串不替换(Cancelled)', 'const e="Cancelled"' in js)
    check('前缀不替换(CancelNow)', 'const f="CancelNow"' in js)
    check('未加引号对象键不替换', 'const g={Cancel:1,Close:2}' in js)
    check('API 命令名不替换', 'invoke("pty_list_shells")' in js)
    check('事件名不替换', 'listen("error",h)' in js)
    check('协议值不替换', 'state==="done"' in js and 'log("running")' in js)
    check('长句替换', '有进程正在运行，关闭此标签页将终止该进程。' in js)
    check('含撇号句子替换', '不再询问正在运行的进程' in js)
    check('AI 占位符替换', '向 Terax 提问任何问题' in js)
    check('设置描述替换', '每个终端保留的历史行数' in js)
    check('退出 Terax 替换', "const j='退出 Terax？'" in js)
    check('.map 文件未动', (dist / 'assets' / 'index-Ab12Cd34.js.map').read_text(encoding='utf-8') == '{"version":3}')

    html = (dist / 'index.html').read_text(encoding='utf-8')
    check('HTML 文本节点+title 替换', '<div title="关闭" name="Close">未保存的更改</div>' in html)
    check('HTML 白名单属性替换(aria-label)', '<span aria-label="关闭">' in html)
    check('HTML 非白名单属性保留(name)', 'name="Close"' in html)
    check('HTML 占位属性替换', 'placeholder="取消"' in html)
    check('HTML lang 改写', '<html lang="zh-CN">' in html)
    check('第二个 html 文件 lang 也改写', '<html lang="zh-CN"><body>ok</body></html>'
          in (dist / 'settings.html').read_text(encoding='utf-8'))

    report = json.loads(report_path.read_text(encoding='utf-8'))
    check('报告 replacements>0', report['summary']['replacements'] > 0)
    check('报告含未命中键', isinstance(report['unused_keys'], list))

    # CRLF 保持:构造带 \r\n 的文件,替换后仍为 \r\n
    crlf = dist / 'assets' / 'crlf.js'
    crlf.write_bytes('const x="Cancel";\r\nconst y="Close";\r\n'.encode('utf-8'))
    patch_dist.main(['--dist', str(dist), '--map', str(map_path()),
                     '--report', str(report_path)])
    check('CRLF 保持', b'\r\n' in crlf.read_bytes() and b'\r\r\n' not in crlf.read_bytes())
    check('幂等重跑', 'const x="取消"' in crlf.read_text(encoding='utf-8'))

    # 失败路径:替换次数低于下限
    empty_dist = tmp / 'dist-empty'
    empty_dist.mkdir()
    (empty_dist / 'a.js').write_text('const q="zzz-unknown";', encoding='utf-8')
    rc2 = patch_dist.main(['--dist', str(empty_dist), '--map', str(map_path()),
                           '--report', str(tmp / 'r2.json'), '--min-replacements', '1'])
    check('零替换退出码 3', rc2 == 3, f'rc={rc2}')

    # 失败路径:dist 不存在
    rc3 = patch_dist.main(['--dist', str(tmp / 'nope'), '--map', str(map_path()),
                           '--report', str(tmp / 'r3.json')])
    check('dist 缺失退出码 2', rc3 == 2, f'rc={rc3}')

    # 失败路径:翻译表含非字符串值
    bad_map = tmp / 'bad-map.json'
    bad_map.write_text('{"Save": 123}', encoding='utf-8')
    rc4 = patch_dist.main(['--dist', str(dist), '--map', str(bad_map),
                           '--report', str(tmp / 'r4.json')])
    check('非法翻译表退出码 2', rc4 == 2, f'rc={rc4}')


# 与上游 v0.9.0 真实文件一致的夹具(摘自 crynta/terax-ai tag v0.9.0)
REAL_CONF = {
    "$schema": "https://schema.tauri.app/config/2",
    "productName": "Terax",
    "version": "0.9.0",
    "identifier": "app.crynta.terax",
    "build": {
        "beforeDevCommand": "pnpm build:cli:dev && pnpm dev",
        "devUrl": "http://localhost:1420",
        "beforeBuildCommand": "pnpm build:cli && pnpm build",
        "frontendDist": "../dist",
        "removeUnusedCommands": True
    },
    "bundle": {
        "active": True,
        "createUpdaterArtifacts": True,
        "targets": "all"
    }
}


def make_upstream(tmp: Path, conf: dict | None = None, name: str = 'terax') -> Path:
    upstream = tmp / name
    (upstream / 'src-tauri').mkdir(parents=True, exist_ok=True)
    (upstream / 'package.json').write_text(json.dumps({
        "name": "terax", "version": "0.9.0",
        "packageManager": "pnpm@11.9.0+sha512.x",
        "scripts": {"build": "tsc && vite build"}
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    (upstream / 'src-tauri' / 'tauri.conf.json').write_text(
        json.dumps(conf or REAL_CONF, ensure_ascii=False, indent=2), encoding='utf-8')
    return upstream


def run_apply(tmp: Path, upstream: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / 'apply_i18n.py'),
         '--upstream', str(upstream),
         '--map', str(map_path()),
         '--report', str(tmp / 'i18n-report.json'), *extra],
        capture_output=True, text=True)


def test_apply_i18n(tmp: Path) -> None:
    print('[apply_i18n]')
    upstream = make_upstream(tmp)
    r = run_apply(tmp, upstream)
    check('apply 退出码 0', r.returncode == 0, r.stderr)

    conf = json.loads((upstream / 'src-tauri' / 'tauri.conf.json').read_text(encoding='utf-8'))
    bbc = conf['build']['beforeBuildCommand']
    check('beforeBuildCommand 已追加补丁调用',
          'patch_dist.py' in bbc and bbc.startswith('pnpm build:cli && pnpm build &&'))
    check('补丁调用带 --dist/--map/--report',
          '--dist' in bbc and '--map' in bbc and '--report' in bbc)
    check('拼接命令不含引号(Tauri Windows 引号陷阱)', '"' not in bbc)
    check('dist 路径按 frontendDist 解析',
          str((upstream / 'dist').resolve()).replace('\\', '/') in bbc.replace('\\', '/'))
    check('createUpdaterArtifacts 已关闭', conf['bundle']['createUpdaterArtifacts'] is False)
    check('productName 已改名', conf['productName'] == 'Terax CN')

    r2 = run_apply(tmp, upstream)
    check('apply 幂等退出码 0', r2.returncode == 0, r2.stderr)
    conf2 = json.loads((upstream / 'src-tauri' / 'tauri.conf.json').read_text(encoding='utf-8'))
    check('幂等:不重复追加', conf2['build']['beforeBuildCommand'].count('patch_dist.py') == 1)

    upstream_nr = make_upstream(tmp, name='terax-nr')
    r3 = run_apply(tmp, upstream_nr, '--no-rename')
    conf3 = json.loads((upstream_nr / 'src-tauri' / 'tauri.conf.json').read_text(encoding='utf-8'))
    check('--no-rename 保留 productName', r3.returncode == 0 and conf3['productName'] == 'Terax')

    # 结构缺失:无 tauri.conf.json
    broken = tmp / 'terax-broken'
    broken.mkdir()
    (broken / 'package.json').write_text('{}', encoding='utf-8')
    r4 = run_apply(tmp, broken)
    check('结构缺失退出码 1', r4.returncode == 1, f'rc={r4.returncode}')

    # 非法翻译表(嵌套结构)
    upstream5 = make_upstream(tmp, name='terax-badmap')
    bad_map = tmp / 'bad2.json'
    bad_map.write_text('{"a": {"b": "c"}}', encoding='utf-8')
    r5 = subprocess.run(
        [sys.executable, str(SCRIPTS / 'apply_i18n.py'), '--upstream', str(upstream5),
         '--map', str(bad_map), '--report', str(tmp / 'r5.json')],
        capture_output=True, text=True)
    check('嵌套翻译表被拒绝', r5.returncode == 1, f'rc={r5.returncode}')

    # 路径含空格:必须提前拦下并报错(Tauri Windows 引号陷阱)
    upstream6 = make_upstream(tmp, name='terax-space')
    spaced = tmp / 'with space'
    spaced.mkdir()
    r6 = subprocess.run(
        [sys.executable, str(SCRIPTS / 'apply_i18n.py'), '--upstream', str(upstream6),
         '--map', str(map_path()), '--report', str(spaced / 'i18n-report.json')],
        capture_output=True, text=True)
    check('报告路径含空格被拒绝', r6.returncode == 1 and '空格' in (r6.stderr + r6.stdout),
          f'rc={r6.returncode}')


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='terax-cn-test-'))
    try:
        test_patch_dist(tmp)
        test_apply_i18n(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'\n通过 {PASS} 项,失败 {FAIL} 项')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
