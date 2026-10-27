# -*- coding: utf-8 -*-
"""检查报告中 replacements 字段的原始存储形态。"""
raw = open('i18n/report-latest.json', encoding='utf-8').read()
i = raw.find('"replacements"')
print(repr(raw[max(0, i - 40):i + 160]))
print('---')
j = raw.find('"generated_at"')
print(repr(raw[j:j + 80]))
