# -*- coding: utf-8 -*-
"""诊断:检查指定键在最近一次构建报告中的命中情况。
兼容两种形态:单腿报告(扁平 schema)与合并报告({平台名: 报告})。
"""
import json
import sys

r = json.load(open('i18n/report-latest.json', encoding='utf-8'))
if 'files' not in r and all(isinstance(v, dict) and 'files' in v for v in r.values()):
    legs = r
else:
    legs = {'default': r}

targets = sys.argv[1:] or ['Open settings', 'Change theme...', 'New Space',
                           'Type a command, > for history, # to find in files']
for leg, rep in legs.items():
    print(f'===== 平台: {leg} =====')
    for t in targets:
        where = [(f, c) for f, hits in rep['files'].items() for k, c in hits.items() if k == t]
        state = '命中' if where else ('未命中(在 unused_keys)' if t in rep['unused_keys'] else '未命中(键不存在)')
        print(f'  {t!r}: {state} {where}')
    print('  summary:', json.dumps(rep['summary'], ensure_ascii=False))
    print('  parse_failed:', rep.get('parse_failed'))
    unused = rep['unused_keys']
    n = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 20
    print(f'  未命中词条({len(unused)}),前 {n}:')
    for k in unused[:n]:
        print('   ', repr(k))
