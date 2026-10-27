# -*- coding: utf-8 -*-
"""诊断:检查指定键在最近一次构建报告中的命中情况。"""
import json

r = json.load(open('i18n/report-latest.json', encoding='utf-8'))

targets = ['Open settings', 'Change theme...', 'New Space',
           'Type a command, > for history, # to find in files']
for t in targets:
    where = [(f, c) for f, hits in r['files'].items() for k, c in hits.items() if k == t]
    state = '命中' if where else ('未命中(在 unused_keys)' if t in r['unused_keys'] else '未命中(不在 unused_keys,键可能不存在!)')
    print(f'{t!r}: {state} {where}')

print('\n--- 命中的文件分布(前 12):')
for f, hits in sorted(r['files'].items(), key=lambda kv: -sum(kv[1].values()))[:12]:
    print(f'  {f}: {sum(hits.values())} 处')

unused = r['unused_keys']
print(f'\n--- 未命中词条({len(unused)} 条),前 40:')
for k in unused[:40]:
    print(repr(k))
