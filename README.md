# Terax 中文版(terax-cn)

Terax([crynta/terax-ai](https://github.com/crynta/terax-ai))的**中文版自动构建工厂**。
本仓库不存放任何上游源码,只保留流程与翻译表;GitHub Actions 每天自动检查官方
release,发现新版本即拉取源码、打上汉化补丁、构建三平台安装包并发布。

## 工作原理

```
每天北京时间 10:00(UTC 02:00,允许几分钟级延迟)
        │
        ▼
┌─ check ─────────────────────────────────────────────┐
│ gh api 取官方最新 release tag(如 v0.9.0)           │
│ 本仓库是否已存在 v0.9.0-cn release?                │
│   已存在 → 结束;不存在 → 触发构建                  │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─ build(4 路并行矩阵,与官方 CI 同构)──────────────┐
│ git clone 官方 tag 源码 → terax/                    │
│ python scripts/apply_i18n.py   ← 唯一的"补丁"动作  │
│   1. tauri.conf.json 的 beforeBuildCommand 追加     │
│      patch_dist.py 调用(vite 产物替换)             │
│   2. createUpdaterArtifacts → false(无官方签名私钥)│
│   3. productName → "Terax CN"(可与官方版并存)      │
│ pnpm install → tauri-action 构建                    │
│   └ vite build 后自动执行 patch_dist.py:           │
│      对 dist 产物做「整串精确全等」的字符串替换     │
│ AppImage 剥离陈旧 libwayland 并重打包(与官方同源)  │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─ publish ───────────────────────────────────────────┐
│ 草稿 release 转正式:tag v<版本>-cn                  │
│ 产物:msi / nsis-exe / deb / rpm / AppImage / dmg   │
└─────────────────────────────────────────────────────┘
```

## 为什么选「构建后 dist 替换」(方案 D 改良版)

`分析.md` 中的 5 种方案,结合 `设计.md` 的三条约束(CI 构建、本仓库最低代码量、
每日自动同步)做如下取舍:

| 方案 | 结论 | 原因 |
|------|------|------|
| A Python 直接改源码 | ❌ | 误伤风险高,官方更新后需重跑,无法审计 |
| B 标准 i18n 改造 | ❌ | 需逐组件改造上游代码,与"最低侵入"冲突,维护成本最高 |
| C Tauri 运行时注入 | ❌ | 需补丁 Rust 源码(补丁点脆弱);MutationObserver 常驻有运行时开销;DOM 替换有英文闪现 |
| E 用户脚本 | ❌ | 仅开发模式有效,打不出可用安装包 |
| **D 改良:构建后替换** | ✅ | 见下 |

改良点(修复了原方案 D 的盲区):

1. **在 `vite build` 之后的产物上替换**,而不是在源码 transform 阶段——JSX 文本
   (如 `<button>Cancel</button>`)在源码里不是字符串字面量,源码级正则抓不到;
   编译产物里它已是普通字符串,全部覆盖;
2. **只做「整个字面量内容 == 翻译键」的全等替换**,不做子串替换:标识符、API 命令
   (`invoke("pty_list_shells")`)、事件名、后端协议值一概不会命中;
3. **翻译表即白名单**:只人工收录确定的 UI 文案;小写协议词(`done`/`error`/
   `running`/`denied` 等)即使肉眼可见也**不收录**,避免前后端状态比对错乱;
4. 唯一构建链侵入点是 `tauri.conf.json` 的 `beforeBuildCommand` 追加(运行时自动
   幂等),上游源码零修改,结构不符时**构建直接失败**,绝不静默产出英文版;
5. 零运行时开销、无闪现、无 DOM 遍历。

## 文件结构

```
.github/workflows/cn-release.yml   # 自动构建流水线(每日检查 + 矩阵构建 + 发布)
scripts/apply_i18n.py              # 挂载补丁到上游源码树(CI 中、构建前运行)
scripts/patch_dist.py              # dist 产物汉化(vite build 后、Tauri 打包前运行)
i18n/translations.json             # 翻译表:扁平 {英文: 中文},人工维护
tests/test_local.py                # 本地测试(无需 pytest,python tests/test_local.py)
分析.md / 设计.md                  # 原始方案分析与设计约束
```

## 如何补充翻译

1. 在应用里看到未翻译的英文界面文案后,把**界面上的完整英文原串**(注意空格、
   省略号 `…`、标点要逐字符一致)加入 `i18n/translations.json`;
2. 提交推送后手动触发一次 workflow(可勾选 force),或在下次官方发版时自动生效;
3. 每次 CI 构建都会产出 `i18n-report-*` 工件,其中 `unused_keys` 是从未命中的词条
   (可据此清理失效键),`files` 里能看到每个词条命中的文件与次数。

翻译键来源:当前 99 条初始词条全部采集自上游 v0.9.0 真实源码
(`CloseDialogs.tsx`、`tool.tsx`、`GeneralSection.tsx`、`AiComposerInput.tsx` 等)。

## 手动操作

- **强制重建当前上游最新版**:Actions → Terax 中文版构建 → Run workflow → 勾选 force;
- **本地测试**:`python tests/test_local.py`(41 项断言,覆盖替换正误例、协议词保护、
  CRLF 保持、防静默英文版、apply 幂等与失败路径)。

## 已知边界

- **动态拼接文案不覆盖**:如 `"3 files have unsaved changes"` 这类带数字/复数变化的
  模板串,整串替换无法命中(会保持英文),属已知取舍;
- **Rust 侧文案不覆盖**:原生对话框、Rust 返回的日志文本不在前端产物里;
- **macOS 包未签名**:首次打开需右键 → 打开;
- **请勿在中文版内点官方检查更新**:会引导到英文官方包,更新请以本仓库 Release 为准;
- 上游若大幅重构构建配置(如 `beforeBuildCommand` 字段变更),CI 会显式失败并给出
  中文错误说明,按提示调整 `apply_i18n.py` 即可。

## 首次启用

1. 在 GitHub 建一个空仓库,推送本项目(GitHub 的 git 操作在 CI 内完成,无需本地
   直连 GitHub);
2. 仓库默认 Actions 权限即可(schedule 触发需要仓库至少被手动启用过一次 workflow);
3. 无需配置任何 Secret:构建不用官方签名密钥,`createUpdaterArtifacts` 已自动关闭。
