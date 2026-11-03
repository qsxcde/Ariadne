# UI 重设计：从聊天机器人到研究工作台（2026-11-03）

> 目标：把「对话即产品」改成「论文即对象、AI 即工具」的研究工作台。
> 关联：[界面清单](ui-screens-2026-11-02.md)、[产品规划](product-plan-2026-11-02.md)

## 1. 为什么现在像 chat robot

| 现象 | 代码位置 | 造成的心理模型 |
|---|---|---|
| 默认路由是 `/` 对话页 | `router/index.ts` → `chat` | 打开产品先看到输入框，像 ChatGPT |
| 左侧栏是会话列表 | `AppSidebar` + `SessionList` | 导航单位是「对话」，不是「论文/课题」 |
| 输入框占据首屏主视觉 | `ChatWorkspace` + `ChatComposer` | 用户以为产品在等自己提问 |
| AI 是一个目的地 | `/` 整页聊天 | 读论文时要跳页才能问 |
| 列表页是卡片网格 | `PaperLibrary` card grid | 信息密度低，像内容社区 |

结论：问题不在配色，在**信息架构**。只要「会话」还是导航主轴、聊天还是默认页面，换皮仍像机器人。

## 2. 设计方向

**风格：学术编辑台（Editorial Workbench）**

- 纸张底色、墨色文字、朱砂强调色；1px 细线分隔，圆角 2–4px，不用大面积阴影。
- 标题用衬线（Noto Serif SC / Source Han Serif），UI 用无衬线（IBM Plex Sans / Noto Sans SC），元数据用等宽（IBM Plex Mono）。
- 信息密度优先：表格、列表、分栏，而不是卡片瀑布。
- 唯一记忆点：**阅读脊柱（Reading Spine）**——正文左侧一条竖向进度轴，标出章节、批注与当前位置，滚动时同步移动。

**核心原则**

1. **对象优先**：导航单位是 Today / 文献库 / 论文 / 集合 / Feed，不是会话。
2. **AI 是检查器**：AI 常驻右侧 Inspector，随当前论文/集合切换；问答只是四个 Tab 之一。
3. **上下文不丢**：顶栏始终显示「课题 › 论文」，切换工具不重置当前对象。
4. **键盘优先**：`⌘K` 全局命令；列表 `j/k` 移动，`Enter` 打开，`/` 搜索。
5. **一屏一件事**：工作区只放当前任务，统计与周报回到 Today。

## 3. 信息架构

```
Today（默认）      今天读什么：继续阅读 / 队列 / 周目标 / 复盘
Library            文献库：表格、筛选、批量导入、集合
Paper              论文工作台：大纲 | 正文/PDF | Inspector
Synthesis          课题综合：问答 / 对比表 / 综述矩阵
Feed               领域跟进：订阅、收件箱式列表
Settings           偏好：模型、提醒、数据
```

- `/` 重定向到 `/today`；对话不再是一级页面。
- 旧 `/` 聊天保留为论文 Inspector 的「问答」Tab；独立会话路由仅用于兼容旧链接。
- 集合不是独立页面，而是 Library 的筛选维度 + Synthesis 的作用域。

## 4. 布局规范

```
┌────────────────────────────────────────────────────────────────────┐
│ TopBar  72px  SciPal / 课题名 / 论文标题   [搜索 ⌘K] [导入] [同步] │
├──────┬──────────────────────────────────────────┬──────────────────┤
│ Rail │ Workspace                                │ Inspector 360px  │
│ 64px │                                          │ 速读 问答 笔记 引用│
│      │  表格 / 阅读器 / 矩阵                     │                  │
│ Today│                                          │  当前论文上下文   │
│ Lib  │                                          │                  │
│ Syn  │                                          │                  │
│ Feed │                                          │                  │
│──────│                                          │                  │
│ 集合 │                                          │                  │
└──────┴──────────────────────────────────────────┴──────────────────┘
```

- Rail：64px 图标 + 文字；集合列表可折叠；底部用户菜单。
- TopBar：面包屑、全局搜索、导入、后台任务状态；不放假头像。
- Inspector：可收起（`⌘\`）；宽度 360px；Tab 状态按论文记忆。
- Reader 三栏：大纲 220px | 正文自适应 | Inspector；正文最大宽度 72ch。
- 断点：≥1280 三栏；1024–1279 Inspector 变抽屉；不承诺移动端（与现有规划一致）。

## 5. 页面设计

### 5.1 Today：桌面，而不是仪表盘

- 左 2/3「继续阅读」：大号衬线标题、作者/年份、进度细线；最多 5 条，其余进队列。
- 右 1/3「本周」：读完/笔记/开放问题/阅读时长，下面是可编辑复盘。
- 底部「队列」横向列表：按优先级排序，可拖拽。
- 不放聊天输入框；顶部只有一个「继续上次阅读」主按钮。

### 5.2 Library：表格，不是卡片

- 列：状态点 | 标题（衬线）| 作者/年份 | venue | 进度 | 最后阅读 | 标签。
- 行高 44px，20 篇一屏；悬停显示「打开 / 加入集合 / 标记已读」。
- 顶部：状态分段控件、集合 chips、搜索、导入、批量选择。
- 空状态给「导入 PDF / 按标识导入」两个动作，不展示插画。

### 5.3 Paper：三栏工作台

- 左：大纲（章节 + 批注数量），点击定位；底部阅读脊柱缩略。
- 中：正文/PDF 切换；顶部只有标题、状态、进度；正文可划词。
- 右 Inspector：
  - 速读：TL;DR / 贡献 / 方法 / 实验 / 局限 / 章节摘要（可回跳）。
  - 问答：紧凑消息流 + 输入框，引用可点开原文；没有整页聊天。
  - 笔记：高亮/笔记/问题列表，点击定位；新建笔记。
  - 引用：OpenAlex 被引/参考文献，点击打开外部页面。
- 底部状态条：页码、进度、最后阅读时间、字数。

### 5.4 Synthesis：矩阵优先

- 顶部集合选择 + 三个 Tab；矩阵表 sticky 首列，单元格可展开引用。
- 对比表与矩阵共用一份数据；导出 CSV/Markdown 放右上。
- 问答作为 Tab，不做全屏聊天。

### 5.5 Feed：收件箱

- 列表行：来源徽标、标题、作者、推荐理由、时间；`J/K` 移动，`S` 保存，`X` 忽略。
- 左侧只放订阅管理（来源 + 关键词），不放大卡片。

## 6. 设计语言（tokens）

```css
:root {
  --paper: #f6f2ea;
  --paper-raised: #fbf8f2;
  --ink: #191713;
  --ink-soft: #4b463d;
  --ink-muted: #6b655c;
  --rule: #d9d2c5;
  --rule-strong: #bfb6a6;
  --accent: #b23a2a;
  --accent-soft: #f3e3de;
  --font-display: "Noto Serif SC", "Source Han Serif SC", serif;
  --font-ui: "IBM Plex Sans", "Noto Sans SC", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, monospace;
}
```

- 强调色只用于：当前导航、引用编号、进度、主按钮；其余用墨色层级。
- 分隔用 1px `--rule`；不使用卡片阴影与毛玻璃。
- 动效 120–180ms：Inspector 滑入、行 hover 显示操作、阅读脊柱跟随滚动。
- 暗色模式后置，不作为首版范围。

## 7. 组件改造清单

| 动作 | 文件 | 说明 |
|---|---|---|
| 新增 | `layouts/WorkbenchShell.vue` | 替换 `AppShell` 的三栏骨架 |
| 新增 | `components/TopBar.vue` | 面包屑、搜索、导入、任务状态 |
| 新增 | `components/WorkbenchRail.vue` | 一级导航 + 集合 + 用户菜单 |
| 新增 | `components/InspectorPanel.vue` | 速读/问答/笔记/引用四 Tab |
| 新增 | `components/CommandPalette.vue` | `⌘K` 命令面板 |
| 新增 | `features/library/components/LibraryTable.vue` | 替换卡片网格 |
| 改造 | `PaperWorkspace.vue` | 三栏编排；Inspector 承载 AI |
| 改造 | `PaperReader.vue` | 去掉页面级 Header，仅保留正文与阅读脊柱 |
| 改造 | `views/TodayView.vue` | 编辑式桌面布局 |
| 改造 | `views/SynthesisView.vue` | 矩阵优先，问答降为 Tab |
| 改造 | `views/FeedView.vue` | 收件箱列表 + 键盘操作 |
| 降级 | `ChatWorkspace.vue` | 仅作为 Inspector 问答 Tab 的内部组件 |
| 调整 | `router/index.ts` | `/` → `/today`；保留旧会话兼容路由 |
| 替换 | `styles/variables.css` | 新色板与字体栈 |

## 8. 分阶段实施

**P0 骨架与令牌**
- 新 tokens、WorkbenchRail、TopBar、WorkbenchShell；`/` 重定向 `/today`。
- 验收：所有现有路由在新骨架下可打开；旧聊天可通过「问答」入口进入；前端 16 用例不回归。

**P1 文献库与论文工作台**
- LibraryTable；Paper 三栏；Inspector 的速读/问答/笔记/引用。
- 验收：20 篇论文一屏可见；从列表到阅读到提问 ≤2 次点击；引用可回跳。

**P2 Today / Synthesis / Feed**
- 编辑式 Today；矩阵优先 Synthesis；收件箱 Feed。
- 验收：一屏完成续读/对比/保存；无整页聊天入口。

**P3 键盘与收尾**
- `⌘K`、`j/k`、`/`、Inspector 收起；空/错/加载三态统一。
- 验收：纯键盘完成「搜索论文 → 打开 → 提问 → 存笔记」。

## 9. 风险与取舍

- **旧链接**：保留 `/sessions/:id/reader` 与旧聊天兼容，避免书签失效。
- **测试**：现有 vitest 只覆盖 composable；P1 需补 LibraryTable 筛选与 Inspector Tab 切换用例。
- **契约**：本次不改后端 API，前端契约无需重生成。
- **移动端**：不做，保持 1280 桌面优先。
- **范围控制**：先做 P0+P1；P2/P3 在验收后决定，不一次性重写全部页面。

## 10. 验收清单

- [ ] 打开产品默认是 Today，不是聊天输入框。
- [ ] 左侧导航是工作流与集合，不是会话列表。
- [ ] 任意页面顶栏都能看到当前课题/论文上下文。
- [ ] 读论文时 AI 在右侧，不跳页。
- [ ] 文献库首屏 ≥20 篇，表格可键盘操作。
- [ ] 没有全屏聊天页作为主入口。
- [ ] 视觉上无卡片瀑布、无蓝色渐变、无毛玻璃。

## 11. 实施进度

- [x] P0 · 设计令牌：纸面/墨色/朱砂色板、衬线+无衬线+等宽字体栈、暖灰阴影、低圆角与动效变量；清理侧栏/输入框/消息气泡/Element Plus 的冷色硬编码
- [x] P0 · WorkbenchShell / WorkbenchRail / TopBar，`/` 重定向 `/today`；搜索/导入/集合通过 query 传入文献库
- [x] P1 · LibraryTable：46px 行高、状态点/进度/标签列、状态分段筛选、悬停操作、集合筛选
- [x] P1 · Paper 三栏：大纲 | 正文/PDF | Inspector 340px
- [x] P1 · Inspector 标签：速读 / 问答 / 笔记 / 术语 / 引用；问答绑定当前论文会话
- [x] P2 · Today：编辑式两栏（继续阅读 / 本周）+ 底部队列条
- [x] P2 · Synthesis：矩阵优先，左侧论文选择器 + 右侧 sticky 首列矩阵
- [x] P2 · Feed：收件箱列表 + 来源徽标 + J/K/S/X/Enter 键盘操作
- [x] P3 · `⌘K` 命令面板：导航 / 导入 / 论文搜索
- [x] P3 · Inspector 收起（`⌘ + \`），状态写入 localStorage
- [x] P3 · 空/错/加载三态统一（StateBlock，覆盖 Today/Library/Synthesis/Feed/Paper/Settings/Inspector）
- [ ] P3 · 全局 j/k 列表导航（Feed 已支持）

> 令牌对比度校验：ink/page 16.0:1、muted/page 5.2:1、white/accent 6.0:1，均满足 WCAG AA。

