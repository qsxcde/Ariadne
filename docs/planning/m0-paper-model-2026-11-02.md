# M0 论文资产层设计（2026-11-02）

> **状态：M0.1–M0.4 已实施（2026-11-03）；M0.5 验收中；当前代码为 schema v8。**
> 范围：SciPal 数据模型重构（schema v8），为「个人研究生 + 阅读进度优先」的论文助手打地基。
> 前置决策：目标用户是个人用户、进度以阅读为主、先做数据模型再上 AI。
> 相关文档：[产品规划](product-plan-2026-11-02.md)、[现状分析](../analysis/status-2026-11-02.md)、[数据模型](../wiki/03-data-model.md)

## 0. 一句话

M0 **只做数据与阅读闭环，不做 AI**。目标是把「论文、阅读状态、批注、集合」变成一等资产，同时**不重写现有摄取/索引链路**，把迁移风险控制在可回滚的范围内。

## 1. 约束与设计决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 用户形态 | 个人研究生、单用户、本地优先 | 不做团队/多租户；权限沿用现有 user/session 模型 |
| 实施顺序 | M0 验收后才进 M1 | 先有 paper / reading state / annotation，AI 功能才有落点 |
| 论文与会话 | **paper 是资产，session 是阅读/索引容器** | 保留 `documents.session_id NOT NULL`，复用现有摄取、快照与 SSE 链路 |
| 阅读状态 | 直接放 `papers`，不拆 `reading_states` | 单用户场景下减少 join 与迁移面；未来做团队时再抽表 |
| 笔记模型 | 单表 `annotations`，`type=highlight/note/question` | 高亮、笔记、问题共享锚点；避免 notes/annotations 双表同步 |
| RAG 命名 | 不改内部 `paper_id` 语义 | `ChunkMetadata.paper_id` 实际是 document id（`storage/sqlite/chunks.py:63-67`）；M0 在 API 层映射真实 paper_id，M2 再统一 |
| 集合检索 | 延后到 M2 | M0 只给 `chunks` 增加 `paper_id`，不碰 `index_snapshots` 的 session scope |
| 导入去重 | 新上传按 SHA-256 去重 | 旧数据保持原样；提供一次性合并脚本，不阻塞迁移 |

## 2. 目标模型

~~~text
users 1 ── N papers 1 ── N documents 1 ── N chunks
                 │  │
                 │  ├── N annotations
                 │  └── N sessions 1 ── N messages
                 │
                 └── N collection_papers N ── 1 collections
                 └── N paper_tags
~~~

关键关系：

- 一篇 paper 可以有多份 document（当前主要是 1 份；为版本/重解析留余地）。
- 一篇 paper 至少有一个 reading session；导入时自动创建，聊天与索引继续挂在 session 上。
- annotation 锚定 paper，并可选择锚定 document / chunk / page / bbox。
- collection 是用户自己的课题/项目；paper 可属于多个 collection。
- 删除 paper 级联删除 document / chunk / annotation / collection 关系；session 归档不触发删除。
- `documents.session_id` 仍为 `NOT NULL` + `ON DELETE CASCADE`；M0 在应用层禁止硬删「有 paper 关联」的 session，避免误删论文文件。

## 3. Schema v8

### 3.1 新表：papers

~~~sql
CREATE TABLE papers (
  id TEXT PRIMARY KEY,
  user_id TEXT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  authors_json TEXT NULL,
  year INTEGER NULL,
  venue TEXT NULL,
  doi TEXT NULL,
  arxiv_id TEXT NULL,
  abstract TEXT NULL,
  url TEXT NULL,
  metadata_json TEXT NULL,
  reading_status TEXT NOT NULL DEFAULT 'inbox',
  progress REAL NOT NULL DEFAULT 0,
  last_location_json TEXT NULL,
  last_read_at TEXT NULL,
  time_spent_seconds INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (reading_status IN ('inbox', 'queued', 'skimming', 'reading', 'read', 'archived')),
  CHECK (progress >= 0 AND progress <= 1)
);
~~~

说明：

- `reading_status` 是唯一进度状态源；`progress` 是 0–1 的冗余快照，便于列表排序，不替代 `last_location_json`。
- `last_location_json` 建议结构：`{document_id, page, chunk_index, section, scroll_ratio}`。
- `time_spent_seconds` 由前端心跳累加；M2 再做 `reading_sessions` 明细表。
- `user_id` 允许 NULL 仅为了兼容历史匿名会话；新导入必须写入当前用户。

### 3.2 新表：annotations

~~~sql
CREATE TABLE annotations (
  id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
  chunk_id TEXT NULL REFERENCES chunks(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  quote TEXT NULL,
  content TEXT NULL,
  color TEXT NULL,
  page_start INTEGER NULL,
  page_end INTEGER NULL,
  bbox_json TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (type IN ('highlight', 'note', 'question'))
);
~~~

- `highlight`：`quote` 必填，`content` 可选；对应原文高亮。
- `note`：`content` 必填，`quote` 可为空；对应段落/章节笔记。
- `question`：`content` 必填；对应「没读懂/待查」。
- 锚点优先级：`chunk_id` > `document_id + page/bbox` > `paper_id`。

### 3.3 新表：collections / collection_papers / paper_tags

~~~sql
CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  user_id TEXT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE collection_papers (
  collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  added_at TEXT NOT NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (collection_id, paper_id)
);

CREATE TABLE paper_tags (
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  PRIMARY KEY (paper_id, tag)
);
~~~

### 3.4 改表：sessions

~~~sql
ALTER TABLE sessions ADD COLUMN paper_id TEXT NULL REFERENCES papers(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_sessions_paper_id ON sessions(paper_id);
~~~

- 新导入：自动创建一个 session，`paper_id` 指向该论文，标题用论文标题。
- 旧会话：回填为「该会话第一篇 document 对应的 paper」；多文档会话仍可通过 documents 访问全部论文。

### 3.5 重建：documents

在 v7 表基础上增加 `paper_id` 与 `file_hash`，保留 `session_id NOT NULL`：

~~~sql
CREATE TABLE documents_new (
  id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  file_hash TEXT NULL,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  error_message TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  parsed_ir_path TEXT NULL,
  parsed_markdown_path TEXT NULL,
  quality_report_path TEXT NULL,
  parser_name TEXT NULL,
  parser_version TEXT NULL,
  parse_quality_status TEXT NULL
);
~~~

`session_id` 保持 `NOT NULL` + `ON DELETE CASCADE`；M0 不拆这个约束，避免重写摄取与索引链路。代价是硬删 session 会级联删文档，因此应用层必须禁止硬删有 paper 关联的 session。

`file_hash` 为 SHA-256；新上传时计算，旧数据留 NULL，由一次性脚本回填。去重查询：

~~~sql
SELECT p.id
FROM documents d JOIN papers p ON p.id = d.paper_id
WHERE p.user_id IS ? AND d.file_hash = ?
LIMIT 1;
~~~

### 3.6 重建：chunks

增加 `paper_id`，保留现有 `session_id` / `document_id` 与全部检索字段：

~~~sql
CREATE TABLE chunks_new (
  id TEXT PRIMARY KEY,
  paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text_excerpt TEXT NOT NULL,
  text_content TEXT NOT NULL,
  type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  section_path_json TEXT NULL,
  page_start INTEGER NULL,
  page_end INTEGER NULL,
  bbox_json TEXT NULL,
  block_ids_json TEXT NULL,
  block_types_json TEXT NULL,
  linked_block_ids_json TEXT NULL,
  confidence REAL NULL
);
~~~

M0 不改变 `ChunkMetadata.paper_id` 的语义；`chunks.paper_id` 只用于按论文查询/未来集合检索。

### 3.7 重建：jobs

增加 `paper_id`，保留 `session_id`：

~~~sql
CREATE TABLE jobs_new (
  id TEXT PRIMARY KEY,
  paper_id TEXT NULL REFERENCES papers(id) ON DELETE CASCADE,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  payload_json TEXT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT NULL,
  finished_at TEXT NULL
);
~~~

### 3.8 不动表

`messages`、`retrieval_indexes`、`index_snapshots` **不在 v8 改动**。理由：M0 的聊天仍以 session 为单位，索引快照继续按 session 构建；M2 做集合检索时再新增 scope 或 collection 快照。

### 3.9 索引

~~~sql
CREATE INDEX idx_papers_user_status ON papers(user_id, reading_status, updated_at DESC);
CREATE UNIQUE INDEX idx_papers_user_doi ON papers(user_id, doi) WHERE doi IS NOT NULL;
CREATE UNIQUE INDEX idx_papers_user_arxiv ON papers(user_id, arxiv_id) WHERE arxiv_id IS NOT NULL;
CREATE INDEX idx_documents_paper_id ON documents(paper_id);
CREATE INDEX idx_documents_file_hash ON documents(file_hash) WHERE file_hash IS NOT NULL;
CREATE INDEX idx_chunks_paper_id ON chunks(paper_id);
CREATE INDEX idx_jobs_paper_id ON jobs(paper_id);
CREATE INDEX idx_annotations_paper ON annotations(paper_id, created_at);
CREATE INDEX idx_annotations_chunk ON annotations(chunk_id);
CREATE INDEX idx_collection_papers_paper ON collection_papers(paper_id);
CREATE INDEX idx_paper_tags_tag ON paper_tags(tag);
~~~

## 4. 迁移方案

### 4.1 顺序

1. `PRAGMA foreign_keys = OFF`。
2. 创建 `papers`、`collections`、`collection_papers`、`paper_tags`、`annotations`。
3. 为每个旧 `documents` 行生成一条 paper，id 用 `paper_<document_id>`（确定性、可回填）。
4. 给 `sessions` 增加 `paper_id`，并回填为该会话最早的 document 对应 paper。
5. 重建 `documents`，写入 `paper_id`，`file_hash` 先为 NULL。
6. 重建 `chunks`，写入 `paper_id`（由 document 映射）。
7. 重建 `jobs`，写入 `paper_id`（有 document_id 时映射，否则 NULL）。
8. 创建索引，`PRAGMA foreign_keys = ON`，执行 `PRAGMA foreign_key_check`，最后 `user_version = 8`。

> fresh DB 的 `_create_initial_schema` 需要按 `users → papers → sessions → collections → documents → chunks → jobs → ...` 的顺序建表；现有迁移路径中 `users` 已在 v5 存在，无需额外处理。

### 4.2 回填规则

- `papers.title`：文件名去掉 `.pdf` 后缀；不做猜测。
- `papers.authors_json` / `year` / `venue` / `doi` / `arxiv_id`：NULL，后续由用户编辑或 M1 元数据补全。
- `papers.user_id`：取所属 session 的 `user_id`；匿名场景允许 NULL。
- `papers.reading_status`：统一 `inbox`。**不根据 document.status 推断已读**，避免制造假进度。
- `papers.created_at/updated_at`：沿用 document 时间。
- `sessions.paper_id`：该 session 最早 document 的 paper；无 document 的会话为 NULL。
- `documents.file_hash`：NULL；由 `scripts/backfill_paper_hashes.py` 在迁移后离线计算。

### 4.3 SQL 草图

~~~sql
INSERT INTO papers (id, user_id, title, reading_status, progress,
                    time_spent_seconds, created_at, updated_at)
SELECT 'paper_' || d.id,
       s.user_id,
       CASE WHEN d.filename LIKE '%.pdf'
            THEN substr(d.filename, 1, length(d.filename) - 4)
            ELSE d.filename END,
       'inbox', 0, 0, d.created_at, d.updated_at
FROM documents d
JOIN sessions s ON s.id = d.session_id;

INSERT INTO documents_new (id, paper_id, session_id, filename, file_path,
                           mime_type, file_size, file_hash, chunk_count,
                           status, error_message, created_at, updated_at,
                           parsed_ir_path, parsed_markdown_path,
                           quality_report_path, parser_name, parser_version,
                           parse_quality_status)
SELECT id, 'paper_' || id, session_id, filename, file_path,
       mime_type, file_size, NULL, chunk_count,
       status, error_message, created_at, updated_at,
       parsed_ir_path, parsed_markdown_path,
       quality_report_path, parser_name, parser_version,
       parse_quality_status
FROM documents;

INSERT INTO chunks_new (id, paper_id, session_id, document_id, section,
                        chunk_index, text_excerpt, text_content, type,
                        created_at, section_path_json, page_start, page_end,
                        bbox_json, block_ids_json, block_types_json,
                        linked_block_ids_json, confidence)
SELECT id, 'paper_' || document_id, session_id, document_id, section,
       chunk_index, text_excerpt, text_content, type,
       created_at, section_path_json, page_start, page_end,
       bbox_json, block_ids_json, block_types_json,
       linked_block_ids_json, confidence
FROM chunks;

UPDATE sessions
SET paper_id = (
  SELECT 'paper_' || d.id
  FROM documents d
  WHERE d.session_id = sessions.id
  ORDER BY d.created_at ASC
  LIMIT 1
);
~~~

### 4.4 安全措施

- 迁移前复制 `backend/data/scipal.db` 到带时间戳的备份；CI 用 v7 fixture 跑迁移测试。
- 迁移在单个事务内执行；失败回滚，不留下半张新表。
- 进入 v8 前先 `conn.commit()`，再执行 `PRAGMA foreign_keys = OFF`；SQLite 在事务内会忽略该 PRAGMA。
- `PRAGMA foreign_key_check` 必须为空；否则中止迁移。
- 先在开发库副本上演练，再对真实库执行。

### 4.5 回滚边界

**schema v8 不是代码级可回滚的**：旧代码插入 `documents` 时不会写 `paper_id`，会触发 NOT NULL。回滚必须同时：

1. 停止服务；
2. 恢复迁移前的 DB 备份；
3. 回退到旧版本代码。

因此发布前备份是硬性要求，不能只靠 git revert。

## 5. API 设计

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/papers` | 上传 PDF：创建 paper + reading session + document + ingestion job |
| GET | `/papers` | 文献库列表；支持 status / collection / tag / q 过滤 |
| GET | `/papers/{paper_id}` | 论文详情：元数据、documents、reading state、annotations、collections、primary_session_id |
| PATCH | `/papers/{paper_id}` | 编辑标题/作者/年份/venue/DOI/arXiv，以及阅读状态与进度 |
| GET | `/papers/{paper_id}/annotations` | 列出高亮/笔记/问题 |
| POST | `/papers/{paper_id}/annotations` | 新建批注 |
| PATCH/DELETE | `/annotations/{annotation_id}` | 编辑/删除批注 |
| GET/POST | `/collections` | 列出/创建集合 |
| PUT/DELETE | `/collections/{collection_id}/papers/{paper_id}` | 加入/移出集合 |
| POST | `/papers/{paper_id}/sessions` | 为同一论文新建对话（可选） |

阅读器继续复用现有按 session/document 的接口：

- `GET /sessions/{session_id}/documents/{document_id}/content`
- `GET /sessions/{session_id}/documents/{document_id}/file`
- `GET /sessions/{session_id}/documents/{document_id}/chunks/{chunk_index}`

`GET /papers/{paper_id}` 返回 `primary_session_id` 与当前 `document_id`，前端不需要自己猜。

契约流程不变：Pydantic schema → `contracts/openapi.json` → `frontend/src/contracts/openapi.d.ts`；CI diff 门禁必须保持。

## 6. 应用层与存储层

新增：

- `storage/sqlite/papers.py`：create / get / list / update_metadata / update_reading_state / find_by_file_hash。
- `storage/sqlite/annotations.py`：create / list_for_paper / update / delete。
- `storage/sqlite/collections.py`：collections + collection_papers + paper_tags。
- `application/papers.py`：导入编排（paper → session → document intake → job）、元数据编辑、阅读状态、去重。
- `application/annotations.py`：锚点校验（chunk 必须属于该 paper/document）、增删改。
- API schemas：`PaperSummary` / `PaperDetail` / `ReadingStatePatch` / `AnnotationCreate` / `CollectionSummary`。

修改：

- `application/documents.py`：`intake_document_upload` 增加 `paper_id` 参数；保留旧签名或做兼容包装。
- `application/ingestion.py`：job payload 带 `paper_id`；日志同时输出 paper_id/session_id/document_id。
- `worker/handlers.py`：读取 paper_id；保持现有 session 级幂等与锁。
- `api/routes/documents.py`：上传入口可新增 paper 绑定，旧 `/sessions/{id}/documents` 保留。
- `domain/access.py`：新增 `paper_is_accessible`；跨用户返回 404，与现有 session 语义一致。

## 7. 前端改造

- `api/papers.ts` / `api/annotations.ts` / `api/collections.ts`。
- `composables/usePaperLibrary.ts`：列表、筛选、导入、去重提示。
- `stores/papers.ts`：论文列表、当前论文、阅读状态；提供 `reset()`，接入现有 `resetClientState`。
- `features/library`：按 status 分组、搜索、集合筛选、导入对话框；现有 `LibraryPanel.vue`（471 行）拆成 `PaperListItem` / `LibraryFilters` / `ImportPaperDialog`。
- `features/reader`：新增 `ReadingProgressBar`、`NotesPanel`、`AnnotationToolbar`；复用 `PaperReader` / `PdfViewer` 的引用定位。
- 路由：新增 `/papers/:paperId`；`AppShell` 的 `showReader` 从 session 判断改为 paper 判断。
- 进度上报：滚动/章节切换节流 2s，`PATCH /papers/{id}` 写入 `progress` 与 `last_location`；离开页面前 flush。
- 批注交互：复用现有划词菜单，新增「高亮 / 记笔记 / 标记问题」；点击笔记回滚到锚点。

## 8. 测试计划

**迁移测试（最高优先级）**

- 构造 v7 fixture：session + 2 documents + chunks + messages + jobs + index_snapshot。
- 运行 `init_db()`，断言：
  - `papers` 数量等于 documents 数量；
  - 每个 document/chunk/job 的 `paper_id` 可解析；
  - `sessions.paper_id` 指向最早 document 的 paper；
  - 旧 `GET /sessions/{id}` 仍返回文档、消息与索引状态；
  - `PRAGMA foreign_key_check` 为空；
  - `user_version = 8`。
- 迁移失败场景：外键冲突时回滚，旧表仍在。

**功能测试**

- paper CRUD、列表过滤、集合/标签。
- 上传去重（同文件第二次返回已有 paper）。
- 阅读状态：状态流转、progress 边界（0/1/越界）、last_location 持久化。
- annotation：高亮/笔记/问题三种类型；chunk 不属于 paper 时拒绝。
- 权限：A 用户不能读 B 的 paper；匿名/开发模式行为与 session 一致。
- 契约：OpenAPI 快照更新，前端生成类型 diff 为零。

**前端测试**

- `usePaperLibrary` 过滤与分组。
- 阅读进度节流与恢复。
- 笔记创建/删除/回滚到锚点。

## 9. 验收标准

| 关卡 | 标准 |
|---|---|
| 迁移 | v7 真实副本迁移成功；fresh DB 直接建 v8；旧会话聊天不回归 |
| 数据完整性 | foreign_key_check 为空；每篇 paper 至少 1 个 document；每篇 document 有 paper_id |
| 阅读闭环 | 导入 → 打开 → 标记在读 → 高亮/笔记 → 关闭再开能续读 |
| 列表 | 按 status/collection/tag 过滤；同文件不重复入库 |
| 质量门禁 | 141 个后端用例全绿；ruff/mypy 通过；前端 test/lint/typecheck/build 通过；契约无 diff |
| 回滚 | 备份可恢复；迁移失败不破坏旧库 |

## 10. 任务拆分与依赖

| 任务 | 内容 | 依赖 |
|---|---|---|
| M0.1 | schema v8 + 迁移 + fresh schema + 迁移测试 | 无 |
| M0.2 | papers / collections / annotations 仓储与用例层 + 去重 | M0.1 |
| M0.3 | `/papers`、`/collections`、`/annotations` API + 契约生成 | M0.2 |
| M0.4 | 前端文献库、阅读器进度、笔记侧栏、路由 | M0.3 |
| M0.5 | 迁移演练、哈希回填/重复合并脚本、端到端验收 | M0.1 |

M1（速读卡等 AI 功能）必须等 **M0.4 + M0.5** 完成后再启动。

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| SQLite 重建表时外键/数据丢失 | 事务 + FK OFF/ON + `foreign_key_check` + 备份 + v7 fixture 测试 |
| 旧多文档会话语义变化 | `sessions.paper_id` 只指向最早文档；旧 session API 不改；文档仍按 session 全量返回 |
| RAG `paper_id` 命名造成误解 | 文档与 API 明确区分 `paper_id` / `document_id`；M0 不改内部语义，M2 统一 |
| 旧重复论文 | 迁移先保留；M0.5 提供按 hash 合并脚本；新上传严格去重 |
| 删除 session 级联删文档 | 现有 API 只归档不硬删；M0 增加保护：有 paper 关联的 session 禁止硬删 |
| 迁移后回滚困难 | 发布前强制备份；回滚 = 恢复 DB + 旧代码，不依赖 schema 降级 |

## 12. 明确不做

- 不做 collection 级检索/多论文对比（M2）。
- 不做 Feed/订阅/提醒（M3，可选）。
- 不做团队共享、多租户、移动端。
- 不重命名 RAG 内部的 `paper_id`。
- 不在 M0 生成任何 AI 摘要；先把数据与阅读闭环跑通。
