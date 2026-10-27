#!/usr/bin/env node
/**
 * Terax 中文版 · 构建后 dist 汉化补丁(AST 版)。
 *
 * 在 `vite build` 之后、Tauri 打包之前运行,对前端产物做「整串精确全等」替换。
 *
 * 为什么用 acorn 解析而不是整文件正则扫描:
 *   最小化产物里存在含引号的 JS 正则字面量(如 /["']/)。整文件逐字符扫描会被
 *   它们带偏状态,之后成片的真实字符串被吞进伪匹配而漏替换(实测主入口块
 *   main-*.js 只命中 2/数百)。acorn 词法保证字符串、正则、模板边界全部正确。
 *
 * 规则:
 *   - 仅当字符串字面量(或无插值的模板串)的完整内容与翻译键完全相等时替换;
 *   - 替换文本用 JSON.stringify 生成,永远是合法 JS 字符串;
 *   - 含 ${} 的模板串、正则、标识符、路径一概不碰;
 *   - HTML 走文本节点(>KEY<)与白名单属性(placeholder/title/aria-label/alt),
 *     并把 lang="en" 改为 zh-CN;CSS 不再处理(UI 文案不在其中);
 *   - 幂等;统计写入 --report(必须在 dist 之外,避免被打进应用)。
 *
 * 用法(由 apply_i18n.py 写入 tauri.conf.json 的 beforeBuildCommand 自动调用):
 *   node patch_dist.mjs --dist <dist目录> --map <translations.json> --report <report.json>
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from './vendor/acorn.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));

// ---------- 参数 ----------
const args = process.argv.slice(2);
function argOf(name) {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
}
function numArg(name, dflt) {
  const v = argOf(name);
  return v === undefined ? dflt : Number(v);
}
const distArg = argOf('--dist');
const mapArg = argOf('--map');
const reportArg = argOf('--report');
const minReplacements = numArg('--min-replacements', 1);

function fail(msg, code) {
  console.error(`[patch-dist] 错误: ${msg}`);
  process.exit(code);
}

// ---------- 标准流强制 UTF-8(Windows runner 默认 cp1252,打印中文会崩) ----------
for (const stream of [process.stdout, process.stderr]) {
  if (stream && typeof stream.setEncoding === 'function') stream.setEncoding('utf8');
}

// ---------- 翻译表 ----------
if (!distArg || !mapArg || !reportArg) fail('缺少 --dist/--map/--report 参数', 2);
const distDir = path.resolve(distArg);
if (!fs.existsSync(distDir) || !fs.statSync(distDir).isDirectory()) {
  fail(`dist 目录不存在: ${distDir}`, 2);
}
let mapping;
try {
  mapping = JSON.parse(fs.readFileSync(mapArg, 'utf8'));
} catch (err) {
  fail(`翻译表读取失败: ${err.message}`, 2);
}
if (typeof mapping !== 'object' || mapping === null || Array.isArray(mapping) || !Object.keys(mapping).length) {
  fail('翻译表必须是非空扁平 {英文: 中文} 映射', 2);
}
const badValues = Object.entries(mapping).filter(([, v]) => typeof v !== 'string' || !v.trim());
if (badValues.length) {
  fail(`翻译表存在非字符串或空白的中文值(前 5 个): ${badValues.slice(0, 5).map(([k]) => k)}`, 2);
}

// ---------- 收集目标文件 ----------
const TARGET_EXT = new Set(['.js', '.mjs', '.html']);
const MAX_BYTES = 100 * 1024 * 1024;
function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(p);
    else if (TARGET_EXT.has(path.extname(entry.name).toLowerCase()) && fs.statSync(p).size <= MAX_BYTES) yield p;
  }
}

// ---------- JS:acorn 解析 + 精确替换 ----------
function collectReplacements(ast, mapping) {
  const out = [];
  function visit(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) {
      for (const child of node) visit(child);
      return;
    }
    if (node.type === 'Literal' && typeof node.value === 'string') {
      const cn = mapping[node.value];
      if (cn !== undefined) out.push({ start: node.start, end: node.end, key: node.value, cn });
      return; // 字符串字面量无子节点
    }
    if (node.type === 'TemplateLiteral' && node.expressions.length === 0) {
      const quasi = node.quasis[0];
      const key = quasi.value.cooked ?? quasi.value.raw;
      const cn = mapping[key];
      if (cn !== undefined) out.push({ start: node.start, end: node.end, key, cn });
      return;
    }
    if (node.type === 'RegExpLiteral') return;
    for (const key of Object.keys(node)) {
      if (key === 'type' || key === 'start' || key === 'end') continue;
      const v = node[key];
      if (v && typeof v === 'object') visit(v);
    }
  }
  visit(ast);
  return out;
}

function patchJsFile(file, mapping) {
  const text = fs.readFileSync(file, 'utf8');
  let ast;
  try {
    ast = parse(text, { ecmaVersion: 'latest', sourceType: 'module', allowHashBang: true });
  } catch (moduleError) {
    try {
      ast = parse(text, { ecmaVersion: 'latest', sourceType: 'script', allowHashBang: true });
    } catch {
      return { parseFailed: true };
    }
  }
  const reps = collectReplacements(ast, mapping);
  const hits = {};
  let output = text;
  reps.sort((a, b) => b.start - a.start); // 从后往前替换,位置不失效
  for (const r of reps) {
    output = output.slice(0, r.start) + JSON.stringify(r.cn) + output.slice(r.end);
    hits[r.key] = (hits[r.key] || 0) + 1;
  }
  return { hits, output };
}

// ---------- HTML:文本节点 + 白名单属性 + lang ----------
function patchHtmlFile(text, mapping) {
  const hits = {};
  for (const en of Object.keys(mapping).sort((a, b) => b.length - a.length)) {
    const cn = mapping[en];
    const textDelimited = `>${en}<`;
    let count = text.split(textDelimited).length - 1;
    if (count) {
      text = text.split(textDelimited).join(`>${cn}<`);
      hits[en] = (hits[en] || 0) + count;
    }
    const attrRe = new RegExp(`(?<![\\w-])(placeholder|title|aria-label|alt)="(${en.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})"`, 'g');
    text = text.replace(attrRe, (_m, attr) => {
      hits[en] = (hits[en] || 0) + 1;
      return `${attr}="${cn}"`;
    });
  }
  const langRe = /(<html[^>]*?\blang=")en(")/g;
  text = text.replace(langRe, (_m, a, b) => {
    hits['(html lang)'] = (hits['(html lang)'] || 0) + 1;
    return `${a}zh-CN${b}`;
  });
  return { text, hits };
}

// ---------- 主流程 ----------
const filesReport = {};
const parseFailed = [];
let patched = 0;
let scanned = 0;

for (const file of walk(distDir)) {
  scanned += 1;
  const rel = path.relative(distDir, file).split(path.sep).join('/');
  if (file.toLowerCase().endsWith('.html')) {
    const text = fs.readFileSync(file, 'utf8');
    const { text: newText, hits } = patchHtmlFile(text, mapping);
    if (Object.keys(hits).length) {
      fs.writeFileSync(file, newText, 'utf8');
      patched += 1;
      filesReport[rel] = hits;
    }
    continue;
  }
  const text = fs.readFileSync(file, 'utf8');
  const result = patchJsFile(file, mapping);
  if (result.parseFailed) {
    parseFailed.push(rel);
    continue;
  }
  if (Object.keys(result.hits).length) {
    fs.writeFileSync(file, result.output, 'utf8');
    patched += 1;
    filesReport[rel] = result.hits;
  }
}

const total = Object.values(filesReport).reduce((sum, hits) => sum + Object.values(hits).reduce((a, b) => a + b, 0), 0);
const keysUsed = new Set(Object.values(filesReport).flatMap((hits) => Object.keys(hits)));
const unused = Object.keys(mapping).filter((k) => !keysUsed.has(k)).sort();
const report = {
  generated_at: new Date().toISOString(),
  dist: distDir,
  keys_total: Object.keys(mapping).length,
  summary: {
    replacements: total,
    files_patched: patched,
    files_scanned: scanned,
    keys_used: keysUsed.size,
  },
  files: filesReport,
  parse_failed: parseFailed,
  unused_keys: unused,
};

fs.mkdirSync(path.dirname(path.resolve(reportArg)), { recursive: true });
fs.writeFileSync(reportArg, JSON.stringify(report, null, 2), 'utf8');

console.log(`[patch-dist] 扫描 ${scanned} 个文件,替换 ${total} 处,命中 ${patched} 个文件,使用 ${keysUsed.size}/${Object.keys(mapping).length} 个词条`);
if (parseFailed.length) {
  console.error(`[patch-dist] 错误: ${parseFailed.length} 个文件无法解析(需人工检查): ${parseFailed.join(', ')}`);
  process.exit(4);
}
if (total < minReplacements) {
  console.error(`[patch-dist] 错误: 替换次数(${total})低于下限(${minReplacements}),疑似上游界面结构大改或翻译表失效,拒绝产出英文版`);
  process.exit(3);
}
