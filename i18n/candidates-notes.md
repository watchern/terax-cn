# i18n/candidates-notes.md — 采集说明（2026-10-28）

数据源：`https://raw.githubusercontent.com/crynta/terax-ai/v0.9.0/`（fetch_content 实抓）。
目录清单来自 GitHub git/trees API（题给 SHA：src / modules / settings 及各子树）。
产出 `candidates.json` 共 **278** 条新键，已逐键对照 `translations.json` 现有 99 条，无重复键。

## 一、分区条数统计

| 区域 | 文件 | 条数 |
|---|---|---|
| settings | ModelsSection(截断)/AgentsSection(截断)/ThemesSection/EditorSection/ShortcutsSection/AboutSection/SettingsApp | 113 |
| command-palette | CommandPalette.tsx、commands.ts | 52 |
| tabs | NewTabMenu、TabBar(截断) | 7 |
| header | Header、SearchInline | 5 |
| statusbar | StatusBar、WorkspaceEnvSelector、CwdBreadcrumb、DiagnosticsBadge | 11 |
| sidebar | SidebarRail | 1 |
| explorer | FileExplorer(截断)、ExplorerSearch、TreeRow、InlineInput | 13 |
| updater | UpdaterDialog、useUpdater | 9 |
| ai/components | AgentSwitcher、FilePicker、SnippetPicker、ChipsRow | 11 |
| spaces | SpaceSwitcher(截断) | 7 |
| editor 模块 | EditorPane(截断)、NewEditorDialog、AiDiffPane、GitDiffPane、EditorStack | 17 |
| source-control | SourceControlPanel(截断)、useSourceControlPanel(截断) | 23 |
| git-history | GitHistoryPane(截断) | 9 |
| workspace | env.ts（无 UI 文案，0 条） | 0 |
| control | 仅 useControlBridge.ts hook（未抓，无 JSX，预计 0 条） | 0 |

## 二、抓取截断 / 失败清单（fetch_content 约 30KB 截断）

- ModelsSection.tsx（46,729B）：截断于 DefaultsBlock 之后；AutocompleteRow、VoiceBlock、CustomEndpointCard 及 settings/components/ProviderKeyCard 的文案未采到。
- AgentsSection.tsx（18,547B）：响应在 CustomInstructionsBlock 中途截断，尾部 Textarea 占位符缺失。
- TabBar.tsx（28,860B）：截断于语言下拉中段；尾部右键菜单（重命名/固定/关闭等）缺失（"Close Tabs to the Right"、"Close Other Tabs" 已在现有表中）。
- FileExplorer.tsx（36,924B）：截断于键盘导航 switch；尾部右键菜单（新建、重命名、删除确认框等）缺失。
- SpaceSwitcher.tsx（19,893B）：截断于 TabRow 关闭按钮 aria-label（疑为 "Close tab"）。
- SourceControlPanel.tsx（49,746B）：截断于约 30KB；提交信息输入区、Commit/Push/Pull/Fetch 按钮、diverged 横幅、行右键菜单、弃用确认 AlertDialog 等大量文案缺失。
- GitHistoryPane.tsx（33,177B）：截断于虚拟行渲染；提交详情弹层（Copy SHA、文件列表、打开差异等）缺失。
- EditorPane.tsx（22,420B）：响应截断，尾部（大文件/空状态提示等）缺失。
- useSourceControlPanel.ts（31,627B）：截断于 commit/push 实现前，尾部的操作提示与错误文案缺失。
- 无网络失败；所有请求均 200。

## 三、安全红线执行记录

- 未收小写疑似枚举/状态值：`detached`（分支标签，git 状态）、`ms`、`columns`（单位）、`untitled`/`untitled.txt`/`example.ts`/`review`/`mytool --fix {file}`（示例值）、`FILE`（扩展名兜底显示）、`OpenAI Compatible`（品牌组合词，建议保留英文）。
- `Deleted` / `Untracked`（useSourceControlPanel 中 statusLabel 字面量）未收：整套状态标签（Modified/Added/…）来自 native 层，零散收两条会造成同一列状态标签中英混杂，建议后续整集处理。
- `"Saved"`（AgentsSection）位于注释代码中，不渲染，未收。
- `no directory`（CwdBreadcrumb）：小写多词展示短语，按规则 5 收录，译"无目录"。
- 单个大写词已收录但建议替换脚本灰度验证：`View`、`Tabs`、`Loading`、`Open`、`Home`、`Files`、`Cloud`、`Contents`、`Custom`、`Copy`、`Create`、`Save`、`Build`、`Theme`、`Background`、`Blur`、`Date`、`Author`、`Subject`、`Changes`、`Name`、`Icon`、`Handle`、`Content`、`Description`、`Instructions`、`Editing`、`Saving`、`Formatter`、`Repository`、`License`、`Website`、`Settings`、`About`、`Editor`、`Models`、`Shortcuts`。其中 **`Spaces` 与 `Tabs` 同时用作命令面板分组键与 item.group 值**（commands.ts：COMMAND_GROUPS 与各 item.group 同字符串），整串替换会两端一致替换，分组逻辑不受影响；若替换脚本做选择性替换则必须保持两端同步。
- 大小写/省略号是不同键，已逐字符区分：`Checking…`(本批,Unicode) ≠ 现有 `Checking...`(ASCII)；`Searching...`(命令面板,ASCII) ≠ `Searching…`(资源管理器,Unicode)；`Command Palette`(对话框标题) ≠ `Command palette`(按钮 title)；`No matches`(大写) ≠ 现有 `no matches`(小写)；`Search command history...`(占位符) ≠ `Search command history`(命令标题)。
- JSX 实体：源码 `Install &amp; restart`，渲染后为 `Install & restart`，键按渲染文本收。
- JSX 跨行文本按空白折叠规则合并为单空格单键：ShortcutsSection 确认描述、ThemesSection 背景说明、StatusBar tooltip、NewEditorDialog 描述等。
- 品牌名保留：Terax、Git、WSL、WebGPU(未涉及)、Vim、Finder、Mica、Windows、GitHub、LM Studio、Ollama、OpenRouter、Hugging Face、Ruff、Prettier、rustfmt、Developer。

## 四、已编目但因 ${} / JSX 拼接不入表的动态串

- AboutSection：`` `Install v${...}` ``、`` `Update to v${...}` ``、`` `${build} · v${version}` ``、`` `v${version}` ``
- UpdaterDialog：`` `Terax v${...} is available` ``、`` `You're on v${...}. Pick your distro...` ``、`` `${progress.toFixed(0)}% — ${formatBytes(...)}` ``、`` `${n} B/KB/MB` ``、`$ {activeCommand}`
- commands.ts：`` `Switch to ${sp.name}` ``、keywords 数组（不显示）
- CommandPalette：`` `theme:${id}` ``、`` `content:${path}:${line}` ``、`` `hist:${cmd}` ``、`` `cmd:${id}` ``、`` `status:${label}` ``、`` `${hit.rel}:${hit.line}` ``
- AgentSwitcher：`` `Agent: ${name}` ``；WorkspaceEnvSelector：`` `WSL: ${distro}` ``、`WSL: {name}`（JSX 拼接前缀 "WSL: "）
- SearchInline：`` `${baseLabel} (${shortcutText})` ``；SpaceSwitcher：`` `Spaces · ${shortcut}` ``
- ThemesSection：`` `Edit ${t.name}` ``、`` `Remove ${t.name}` ``（aria-label）、`` `${file.name}: ${result.error}` ``、`` `${file.name}: not an image` ``
- SourceControlPanel：`` `Commit with ${commitShortcut}.` ``、`` `${originalPath} → ${path}` ``；useSourceControlPanel：`` `No local commits to push to ${upstream}.` ``、`` `Pushes to ${upstream}.` ``、`` `R ${a} -> ${b}` `` 等提交信息生成 prompt（非 UI）
- EditorPane：`` `${formatter} format failed` ``；EditorSection：`` `{size} px` ``（SelectItem）；TabBar：`Mode: {resolveDisplayName(...)}`（"Mode: " 为半句前缀，未收）；AiDiffPane/GitDiffPane：`` `+${added}` ``/`` `−${removed}` ``
- 跨节点拼接的半句（未收，属"半句话片段"）：AgentsSection "Reusable instructions you can drop into any prompt with" + `#handle` + "."；"No snippets yet. Create one and insert it with" + `#handle` + " in the AI input."；ModelsSection "The model id loaded in LM Studio — see the server's" + `/v1/models` + " page."；"Browse ids at " + `openrouter.ai/models` + "."

## 五、待证项 / 建议下一步

1. 抓 `src/modules/shortcuts/shortcuts.ts`：快捷键 label/group 是纯展示字符串（ShortcutsSection 与命令面板直接渲染），覆盖率收益最大。
2. 抓 `src/settings/components/` 子树（ProviderKeyCard、LspServersGroup、SettingRow、SectionHeader）与 `src/modules/agents/`（AgentLauncherPanel、NotificationBell）。
3. ai/components 下大文件（AiMiniWindow 19KB、AiStatusBarControls 21KB、AiChat 20KB、AiComposerInput 10KB、AiToolApproval、PlanDiffReview、TodoStrip、SelectionAskAi）均未抓。
4. markdown / preview / terminal / theme / lsp 模块未列目录。
5. 截断文件的缺失尾部需换途径（如按行范围抓取）补采，尤其 SourceControlPanel 与 FileExplorer 的右键菜单与确认框。
6. GeneralSection.tsx（21.7KB）未抓：现有 99 条已覆盖 General 区大部分文案，剩余增量待核对。
