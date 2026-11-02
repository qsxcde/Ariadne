# 07 前端

目录：`frontend/`
技术栈：Vue 3（`<script setup>` + TS）+ Element Plus + Vite 8 + vue-router（已安装）
状态管理：无 Pinia/Vuex，使用模块级单例 `ref` 的 composables

## 1. 脚本与依赖

`frontend/package.json`：

| 脚本 | 命令 |
|---|---|
| `dev` | `vite`（默认 `http://localhost:5173`） |
| `build` | `vue-tsc -b && vite build` |
| `lint` | `eslint .` |
| `preview` | `vite preview` |

运行时依赖：`vue ^3.5`、`vue-router ^4.6`、`element-plus ^2.12`、`@element-plus/icons-vue`、`markdown-it ^14.2`。
开发依赖：`vite ^8`、`@vitejs/plugin-vue`、`typescript ~6.0`、`vue-tsc`、`eslint`、`typescript-eslint`、`eslint-plugin-vue`。

`vite.config.ts` 注册 Vue 插件、dev server 代理（`/auth`、`/sessions`、`/health` → `VITE_DEV_PROXY_TARGET`，默认 `http://127.0.0.1:8000`）与 `manualChunks` 分包；没有路径别名。

## 2. 目录结构

```
frontend/
├── index.html
├── vite.config.ts
├── package.json
├── .env.example                 # VITE_API_BASE_URL=http://127.0.0.1:8000
├── prototypes/                  # 静态 HTML + 截图设计稿，不参与构建
└── src/
    ├── main.ts                  # 注册 Element Plus + router，mount #app
    ├── App.vue                  # 三态：loading / 未登录 / 主界面
    ├── layouts/AppShell.vue     # 页面级编排，唯一调用 usePaperChat()
    ├── contracts/openapi.d.ts   # 由 contracts/openapi.json 生成，禁止手改
    ├── api/                     # client / sse / auth / chat / documents / library / ...
    │   └── types.ts             # 后端契约别名映射（Schemas["Xxx"]）
    ├── types/                   # view.ts 视图模型、index.ts 汇总
    ├── router/index.ts          # hash 路由表，已在 main.ts 注册
    ├── utils/markdown.ts        # markdown-it token → MarkdownNode 树
    ├── styles/                  # variables / base / layout / element-plus
    ├── views/LoginView.vue
    ├── constants/               # app / chat / upload
    ├── composables/             # useAuth useSessionState useChatStream usePaperChat
    │                            # useLibrary usePaperReader useSourcePreview useClientReset
    └── components/              # 22 个 SFC（待 P5 按域拆分）
```

## 3. 组件树

```
App.vue
├── LoginView.vue                      (未登录)
└── AppLayout.vue                      (已登录)
    ├── AppSidebar.vue
    │   ├── SidebarHeader.vue
    │   ├── SessionList.vue
    │   │   └── SessionListItem.vue
    │   │       └── SessionActionsMenu.vue
    │   └── RenameSessionDialog.vue
    └── ChatWorkspace.vue
        ├── ChatHeaderBar.vue
        ├── MessageList.vue
        │   └── MessageBubble.vue
        │       ├── MarkdownContent.vue
        │       │   └── MarkdownNodeRenderer.vue
        │       └── MessageActions.vue
        ├── UploadStatusCard.vue
        └── ChatComposer.vue
            └── ComposerTools.vue
```

| 组件 | 职责 | 主要 props / emits |
|---|---|---|
| `App.vue` | 认证门禁 + 骨架屏 | — |
| `LoginView.vue` | 登录/注册切换表单 | 无 props |
| `AppLayout.vue` | 布局编排，向两侧分发事件 | 调用 `usePaperChat()` |
| `AppSidebar.vue` | 侧栏容器（折叠/展开），持有重命名弹窗状态 | props `collapsed, indexedChunks, isUploading, recentSessions, username` |
| `SidebarHeader.vue` | 品牌区 + 新建 + 折叠 | props `collapsed, isBusy`；emits `createSession, toggleCollapse` |
| `SessionList.vue` | 列表滚动容器 | props `collapsed, items` |
| `SessionListItem.vue` | 单条会话 | props `id, title, description, active, collapsed, isPinned` |
| `SessionActionsMenu.vue` | 「⋯」菜单：重命名/置顶/删除 | props `isPinned` |
| `RenameSessionDialog.vue` | 重命名弹窗 | props `visible, initialTitle` |
| `ChatWorkspace.vue` | 对话区容器，转发事件 | 10 个 props |
| `ChatHeaderBar.vue` | 会话标题 + 论文提示 | props `paperHint, sessionTitle` |
| `MessageList.vue` | 空态欢迎页 / 消息列表，滚动跟随（阈值 120/240px） | props `hasPaper, isStreaming, messages, suggestedPrompts` |
| `MessageBubble.vue` | 单条气泡；pending 显示「正在检索论文并生成回答...」 | props `message, pending` |
| `MarkdownContent.vue` | markdown → 安全 VNode 渲染入口 | props `text` |
| `MarkdownNodeRenderer.vue` | 递归渲染 `MarkdownNode` | props `node` |
| `MessageActions.vue` | 复制回答（`navigator.clipboard`） | props `content` |
| `ChatComposer.vue` | 输入框 / 发送 / 选择文件 | props `draft, isStreaming, isUploading, uploadStatus` |
| `ComposerTools.vue` | 工具条按钮（检索开关 / 更多 / 上传），多为 UI 占位 | props `disabled, state` |
| `UploadStatusCard.vue` | 上传/解析/索引进度卡 | props `status` |

Markdown 渲染链：`markdown-it` 解析 → `parseMarkdown()` 生成白名单 `MarkdownNode` 树 → `MarkdownNodeRenderer` 递归渲染，**不使用 `v-html`**。

## 4. 数据流

```
App.vue ──useAuth()──▶ api.getMe / login / register
AppLayout.vue ──usePaperChat()──┬── useSessionState() ──▶ GET/POST/PATCH/DELETE /sessions*
                                └── useChatStream()   ──▶ POST /sessions/{id}/messages (SSE)
```

### 4.1 `useAuth`

模块级单例 `isAuthenticated / user / loading`。`checkAuth()` 在存在 token 时调 `getMe()`，失败 `clearToken()`。登录成功写 `localStorage["scipal_token"]`。

### 4.2 `useSessionState`

持有 `sessions / documents / paperSession / isUploading / uploadStatus`；派生 `hasPaper / displayFileName / indexedChunks`。

上传流程是**轮询**而非 SSE：

```
handleUpload(file)
  → uploadDocument(sessionId, file)          → 202
  → 每 1000ms getSession(sessionId)
        status ready|failed → 结束
        最多 600 次（约 10 分钟）
```

`STATUS_LABELS` 把文档状态映射为中文提示。`DEMO_SESSION_ID = "demo-session"` 用于演示数据。

### 4.3 `useChatStream`

持有 `draft / isStreaming / messages`。

- `sendMessage(text, sessionId)`：先本地乐观插入 user 消息与空 assistant 消息，再消费 `streamChat()`。
- `replaceMessages()`：用会话快照里的持久化消息整体替换。
- `useDemoPaper()`：注入演示消息。
- 重试：`SSE_RETRY_MAX_ATTEMPTS=2`，退避 1s / 2s，每次重试重置累积文本；`AbortError` 直接终止且不报错。
- **只处理 `token` / `sources` / `error` 三类事件，`status` 事件被忽略。**

### 4.4 `usePaperChat`

组合层，对外唯一 API：统一 `errorMessage`、派生 `currentSessionTitle / currentPaperHint`；无会话时自动建会话；`demo-session` 下拦截发送并提示"示例论文仅供预览…"。

## 5. SSE 客户端实现

`src/api.ts` 使用 `fetch` + `res.body.getReader()` + `TextDecoder(..., {stream:true})`，**不用 `EventSource`**（需要 POST 与 `Authorization` 头）。

解析算法：

1. 按 `\n` 切行，保留末尾残行。
2. 以 `data: ` 前缀的行累积到 `dataBuffer`。
3. 空行作为事件边界 → `JSON.parse`；解析失败静默丢弃该帧。
4. `type === "done"` 直接结束生成器。
5. 只消费 `data:` 行，不解析 `event:` / `id:` / `retry:`，不识别 `[DONE]`。

事件联合类型 `MessageChunk`（`api.ts`）：

```ts
| { type: "token"; value: string }
| { type: "sources"; value: SourceRef[] }
| { type: "status"; value: string }
| { type: "error"; value: string }
| { type: "done" }
```

错误处理：非 2xx 时读 `{detail}`，缺失则用中文兜底文案；`res.body` 为空 → 抛"后端没有返回可读取的流式响应"。

## 6. 类型镜像

- 后端契约类型（`SourceRef / PaperDocument / PersistedMessage / RetrievalIndexSummary / SessionSummary / SessionSnapshot / MessageChunk`）定义在 `api.ts`。
- `types.ts` 只放视图模型（`PaperSession / ChatMessageViewModel / SidebarSessionItem / SessionSnapshotViewModel / UploadStatus / ComposerToolState / SuggestedPrompt`），并反向 import `api.ts` 类型。
- **没有共享契约包**，字段为手写 snake_case 镜像；后端改字段前端不会报编译错误。

## 7. 已知问题

1. **`status` / `warning` 事件仍未呈现**：`useChatStream` 收到后直接忽略，用户看不到「等待索引 / 检索中 / 生成中」。
2. **工具条部分按钮是占位**：`ComposerTools` 的检索开关/更多未接后端能力。
3. **上传轮询有上限**：约 10 分钟（600 × 1s）后停止轮询，界面停留在最后一个状态。
4. **笔记锚点仍是 paper/quote 级**：M0 的批注面板支持高亮、笔记、问题，但 PDF 原页 bbox 高亮层尚未接入。
5. **旧 Chat 页仍保留**：目标形态是 Reader/Synthesis 侧栏问答；当前 `/` 仍是独立聊天页，`/sessions/:sessionId/reader` 保留为 legacy。

> 路由已注册，`/documents`、`/papers`、`/annotations`、`/collections` 均已加入 Vite dev proxy。

## 8. 论文资产界面（v8）

| 路由 | 组件 | 用途 |
|---|---|---|
| `/today` | `views/TodayView.vue` | 继续阅读、阅读队列、本周完成 |
| `/synthesis` | `views/SynthesisView.vue` | 集合选择、问答 / 对比表 / 综述矩阵三 Tab |
| `/feed` | `views/FeedView.vue` | 订阅、Feed 刷新、保存到队列/忽略 |
| `/library` | `features/library/components/PaperLibrary.vue` | 论文列表、状态/集合/标签筛选、批量上传、按 arXiv/DOI/链接导入 |
| `/papers/:paperId` | `features/reader/components/PaperWorkspace.vue` | 论文详情、阅读器、进度、笔记侧栏、元数据编辑 |
| `/sessions/:sessionId/reader` | `features/reader/components/PaperReader.vue` | legacy 会话阅读器 |
| `/settings` | `views/SettingsView.vue` | 数据/隐私/模型说明；提醒与 Digest 设置 |
| `/` | `ChatWorkspace` | 对话（legacy 主入口） |

状态与 API：

- `composables/usePapers.ts`：文献库、当前论文、筛选、阅读状态、笔记；通过 `stores/index.ts` 导出。
- `api/papers.ts`：list / get / upload / import / update；`api/annotations.ts`、`api/collections.ts` 对应批注与集合。
- 进度：`PaperReader` 滚动时 emit `progress`，`PaperWorkspace` 1.2s 节流后 `PATCH /papers/{id}`；重开时用 `initial-progress` 恢复滚动位置。
- 笔记：选中正文点「记笔记」emit `note`，保存为 highlight；右侧栏可新增 note、删除批注。
- 速读卡：右侧栏「生成速读卡」调用 POST /papers/{id}/brief，展示 TL;DR/贡献/方法/实验/局限/要点；章节摘要列表点击后经 `findBlockBySection` 定位并高亮正文块。
- 术语表/引用：右侧栏可生成术语表、查询 OpenAlex 引用关系。
- 通知：Settings 显示未读通知，支持「检查引用更新 / 检查新版本」与 Webhook 投递；邮件需另配 SMTP。
- 划词动作：解释/翻译/简化调用 POST /papers/{id}/explain；追问仍转为高亮笔记。
- 结构化块：table / formula 块右上角提供「解释表格 / 解释公式」，复用同一 explain 端点。
- 元数据：阅读工作台「编辑信息」弹窗 PATCH /papers/{id}，可改标题/作者/年份/venue/DOI/arXiv/链接/摘要。
- 阅读时长：工作台每 5s 累计可见停留时间，满 60s 或离开页面时 POST /papers/{id}/reading-time；Today 展示今日/本周时长。
- Synthesis：三个 Tab——问答、对比表、综述矩阵；矩阵按方法/数据集/指标/局限排列并显示覆盖率，可导出 Markdown。
- Today：按 reading_status 展示继续阅读/队列/本周读完；目标当前固定 3 篇；本周笔记/开放问题/复盘文字来自 GET /review/weekly，阅读时长来自 GET /papers/stats；复盘通过 PUT /review/weekly/note 保存。
- 集合进度：`CollectionSummary.by_status` 提供各状态计数，文献库集合下拉与 Synthesis 工具条显示已读/在读/待读。
- 导出：阅读器笔记导出 Markdown；Synthesis 对比表导出 CSV、综述矩阵导出 Markdown；文献库导出 BibTeX。
- 设置：提醒开关与 Digest 频率写入 /settings/alerts；当前只保存本地偏好，邮件/推送投递尚未接入。

## 9. 本地开发

```bash
cd frontend
npm install
cp .env.example .env        # 按需修改 VITE_API_BASE_URL
npm run dev                 # http://localhost:5173
npm run build               # 类型检查 + 产物构建
npm run lint
```

后端需先启动（见 [10 开发与运维](10-development.md)），并确保 `JWT_SECRET_KEY` 的配置与登录方式匹配：

- 未配置 `JWT_SECRET_KEY` 且 `APP_ENV` 为开发类取值：后端处于匿名旁路，数据接口免鉴权，但 `/auth/login`、`/auth/register` 返回 400 `Auth not configured`。前端 `useAuth.checkAuth()` 在无 token 时直接置为未登录态，因此界面会停在 `LoginView` 且无法登录——本地无鉴权联调需要手动写入 `localStorage.setItem("scipal_token", "dev")`。
- `APP_ENV=production` 且缺 `JWT_SECRET_KEY`：数据接口统一 503 `Authentication is not configured`（fail closed）。
- 配置了 `JWT_SECRET_KEY`：走正常注册/登录流程。
