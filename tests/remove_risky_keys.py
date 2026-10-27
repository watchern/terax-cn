# -*- coding: utf-8 -*-
"""从翻译表中移除运行时风险键(failed / Home),并校验 JSON。"""
import io
import json

p = 'i18n/translations.json'
lines = io.open(p, encoding='utf-8').read().splitlines(keepends=True)
remove = {'"failed": "失败",', '"Home": "主目录",'}
out = [line for line in lines if line.strip() not in remove]
io.open(p, 'w', encoding='utf-8', newline='\n').writelines(out)
m = json.load(open(p, encoding='utf-8'))
assert 'failed' not in m and 'Home' not in m, '移除失败'
print('词条数:', len(m), '| failed/Home 已移除')
