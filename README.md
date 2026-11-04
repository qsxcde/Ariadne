<div align="center">

<h1 align="center">Ariadne</h1>

<p align="center">面向学术论文阅读的 RAG 问答与文献工作台</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3.5-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-blue">
</p>

[功能特性](#功能特性) · [快速开始](#快速开始) · [配置说明](#配置说明) · [开发与测试](#开发与测试) · [文档](#文档)

</div>

---

## 简介

Ariadne 是一个面向学术论文阅读场景的 RAG 问答系统与文献工作台。用户上传 PDF 后，系统在后台完成文档解析、切块、向量化与索引构建，并基于论文内容提供**带来源引用的中文流式回答**；围绕这条主线，还提供文献库、批注、阅读统计、集合问答、多论文对比与 arXiv 跟进等能力。

设计上强调三点：

- **异步可观测**：上传立即返回 `202 Accepted`，文档、任务与会话状态均可查询，进程重启后可恢复中断任务。
- **索引原子提交**：检索索引以不可变快照（snapshot）组织，先构建候选再原子提升，构建失败不污染已可用索引。
- **回答可追溯**：回答必须给出章节级来源引用，服务端会与检索到的章节集合做一致性校验。

当前为 PC Web 应用，单进程部署；能力边界与已知缺口见[已知限制](#已知限制)与 [docs/wiki](docs/wiki/README.md)。

## 功能特性

### 文献资产管理

- 上传文本型 PDF，或按 arXiv / DOI / 链接导入并自动抓取元数据。
- 文献库支持按状态、集合、标签与标题过滤，支持集合与批注管理。
- 论文详情、引用信息，以及 BibTeX / CSL JSON / Markdown 导出。
- Zotero / Notion 导出集成。

### 阅读辅助

- 内置 PDF 阅读器与结构化正文渲染，支持从回答引用回跳原文段落。
- 划词解释、速读卡、术语表与引用摘要。
- 阅读时长记录、按天/按论文统计与每周复盘。

### RAG 问答与研究 Agent

- 单会话内多文档累积索引，回答严格基于论文上下文。
- BM25 + Dense 混合召回、RRF 融合、Cross-Encoder 重排与上下文扩展。
- 快速问答与 Agent 研究双模式：Agent 可多步检索、读取片段并展示可回放的运行轨迹。
- SSE 流式输出，事件类型为 `status`、`run_started`、`tool_call`、`tool_result`、`token`、`sources`、`done`（异常时附加 `warning` / `error`）。
- DeepSeek 为主模型，可在开启配置后降级到 GLM / Qwen / Ollama。

### 综合与跟进

- 集合问答与多论文对比。
- arXiv 订阅与 Feed 刷新、忽略与收藏。
- 新引用 / 新版本提醒、站内通知与 SMTP 邮件投递。

### 工程质量

- 摄取任务由进程内 `InProcessJobRunner` 异步推进，任务领取使用 CAS，避免重复执行。
- commit-based 索引快照：`building → ready`，旧快照转 `stale`，失败时回滚。
- OpenAPI 契约快照、自动生成的 README 端点表与前端类型生成，避免契约漂移。
- pytest 分层测试，并用 AST 静态校验分层依赖边界。

## 技术栈

| 层次 | 技术选型 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus |
| 后端 API | FastAPI + Pydantic v2 + pydantic-settings |
| 异步任务 | `InProcessJobRunner`（daemon 线程 + 进程内 FIFO 队列） |
| PDF 解析 | MinerU（云 API / 本地）+ pypdf，顺序降级 |
| Embedding | sentence-transformers（本地）/ OpenAI 兼容远程 API |
| 向量检索 | FAISS `IndexFlatL2` |
| 关键词检索 | 自实现 BM25（中英混合分词） |
| 重排序 | 远程 rerank API → 本地 cross-encoder → 原序截断 |
| LLM | OpenAI Python SDK，DeepSeek 主用 |
| Agent | LangChain 1.x `create_agent` + LangGraph 1.2（仅适配器层引入） |
| 持久化 | SQLite（WAL）+ 本地文件目录 |
| 测试与质量 | pytest、Vitest、ESLint、Prettier、ruff、mypy |

## 系统架构

```
┌────────────────────────────────────────────────────────────┐
│ 前端  frontend/src（Vue 3 + TypeScript + Element Plus）     │
│       REST + SSE（Bearer JWT）                              │
└───────────────────────────┬────────────────────────────────┘
                            │ HTTP / text-event-stream
┌───────────────────────────▼────────────────────────────────┐
│ 接口层  backend/api         路由、传输契约、SSE 编码、鉴权   │
├────────────────────────────────────────────────────────────┤
│ 应用层  backend/application library / reading / ingestion /  │
│         conversation / follow / synthesis / agent           │
├────────────────────────────────────────────────────────────┤
│ 领域层  backend/domain      模型、状态机、授权规则、领域异常  │
├────────────────────────────────────────────────────────────┤
│ 能力层  backend/rag         摄取、切块、索引、检索、生成      │
├────────────────────────────────────────────────────────────┤
│ 适配层  backend/adapters    LLM / Embedding / Vector /       │
│         Parser / Rerank / Agent（LangGraph）                 │
├────────────────────────────────────────────────────────────┤
│ 存储层  backend/storage     SQLite（WAL）+ 本地文件目录      │
└────────────────────────────────────────────────────────────┘
```

依赖方向单向：`api → application → (domain, rag, storage)`；`adapters` 实现 `domain/ports.py` 定义的端口，由 `composition` 完成装配。

**上传与异步摄取**

1. `POST /sessions/{id}/documents` 校验会话与文件后落盘，创建 `documents`（`uploaded`）与 `jobs`（`queued`）记录，返回 `202`。
2. 后台 runner 依次推进 `uploaded → parsing → parsed → chunked → indexing → ready`。
3. 索引先构建候选快照，再原子提升为 active `ready` 快照；任一阶段失败则文档、job 与快照同步标记为 `failed`。

**聊天与流式回答**

1. `POST /sessions/{id}/messages` 先持久化用户消息，并等待会话存在 active ready 快照。
2. 基于快照检索上下文，调用 LLM 生成中文回答。
3. 通过 SSE 返回 `sources` 与 `done`，持久化 assistant 消息；生成中断时以 `failed` 状态落库并保留已生成内容。

**Agent 研究**

1. 请求携带 `mode: "agent"` 时，服务端创建 `agent_runs`，通过 LangGraph `create_agent` 调用 3 个只读工具。
2. 工具步骤、来源与摘要写入 `agent_steps`；SSE 推送 `run_started` / `tool_call` / `tool_result` 与最终答案。
3. 回答消息通过 `run_id` 关联运行，可随时按 `GET /sessions/{id}/runs/{run_id}` 回放。

完整链路（状态机、数据模型、SSE 协议）见 [docs/wiki](docs/wiki/README.md)。

## 目录结构

```
Ariadne/
├── backend/
│   ├── pyproject.toml              # 依赖、可选组与工具配置
│   ├── .env.example                # 后端环境变量模板
│   └── src/
│       ├── backend/
│       │   ├── main.py             # FastAPI 装配根与启动恢复
│       │   ├── config.py           # RuntimeSettings 与路径解析
│       │   ├── api/                # 路由、schema、依赖、SSE、错误映射
│       │   ├── application/        # 用例层：library/reading/ingestion/conversation/follow/synthesis
│       │   ├── domain/             # 领域模型、状态、授权、异常、端口
│       │   ├── rag/                # 摄取、切块、索引、检索、生成
│       │   ├── adapters/           # LLM、Embedding、FAISS、解析器、重排
│       │   ├── storage/            # 路径布局与 SQLite 仓储
│       │   ├── worker/             # 进程内任务 runner 与 handler
│       │   ├── composition/        # 配置到具体能力的装配
│       │   ├── prompts/            # prompts.toml 与加载器
│       │   └── scripts/            # OpenAPI / 端点表 / 迁移 / 索引回收
│       └── ariadne_eval/            # 离线评测 CLI
├── frontend/
│   └── src/
│       ├── api/                    # HTTP 与 SSE 客户端、契约类型
│       ├── app/                    # 应用外壳、布局与路由
│       ├── features/               # chat / library / reader / sessions
│       ├── pages/                  # today / library / paper / synthesis / feed / settings
│       └── shared/                 # 组件、composables、样式、工具
├── contracts/openapi.json          # OpenAPI 契约快照
├── tests/                          # unit / integration / architecture / contracts / network
├── scripts/                        # 评测与集成测试脚本
├── docker/                         # 前后端与 mock-llm 镜像
├── docs/                           # wiki / analysis / planning
├── openspec/                       # spec-driven change 归档
└── docker-compose.*.yml
```

## 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|---|---|---|
| Python | >= 3.11 | 后端运行时 |
| [uv](https://github.com/astral-sh/uv) | 最新版 | 后端依赖与虚拟环境管理 |
| Node.js | 20.19+ 或 22.12+（CI 使用 22） | 前端构建 |
| npm | 随 Node.js 安装 | 前端依赖管理 |
| Docker + Compose v2 | 可选 | 容器化部署与集成测试 |

按默认配置，首次运行可能需要下载 Embedding、Reranker、MinerU 等模型，请预留数 GB 磁盘空间与稳定网络。

### 1. 克隆仓库

```bash
git clone <repo-url>
cd Ariadne
```

### 2. 安装依赖

后端（在仓库根目录执行，虚拟环境将创建在 `backend/.venv`）：

```bash
uv sync --project backend --extra dev --group eval
```

> 运行时依赖与 `dev` 可选组位于 `backend/pyproject.toml` 的 `[project.optional-dependencies]`，评测依赖为 `[dependency-groups] eval`；`backend/uv.lock` 锁定精确版本。仅运行服务时可省略 `--extra dev --group eval`。

前端：

```bash
cd frontend
npm install
```

### 3. 配置环境变量

```bash
cp backend/.env.example backend/.env
```

至少填写 `DEEPSEEK_API_KEY`；如需账号登录与多用户隔离，再生成并填写 `JWT_SECRET_KEY`：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

完整变量说明见[配置说明](#配置说明)。

### 4. 启动服务

后端（在仓库根目录执行）：

```bash
uv run --project backend uvicorn backend.main:app --reload
```

前端（另开终端）：

```bash
cd frontend
npm run dev
```

| 服务 | 地址 |
|---|---|
| 前端 | <http://localhost:5173> |
| 后端 | <http://localhost:8000> |
| OpenAPI 文档 | <http://localhost:8000/docs> |
| 健康检查 | <http://localhost:8000/health> |

未设置 `VITE_API_BASE_URL` 时，前端使用同源相对路径，由 Vite dev server 将 `/auth`、`/sessions`、`/papers` 等前缀代理到 `http://127.0.0.1:8000`（可用 `VITE_DEV_PROXY_TARGET` 覆盖）。

## 使用流程

1. 打开前端页面，注册或登录账号（开发环境未配置 `JWT_SECRET_KEY` 时以匿名 dev 用户放行）。
2. 在文献库上传论文 PDF，或按 arXiv / DOI / 链接导入。
3. 等待后台任务完成解析与索引提交，文档状态变为 `ready`。
4. 在论文工作台或会话中提问，查看带来源引用的流式回答。
5. 可选：使用划词解释、速读卡、术语表、批注、集合问答、多论文对比与周报。

## 配置说明

后端**只读取 `backend/.env`**；仓库根目录的 `.env` 会被忽略，并在启动日志中打印告警。

常用变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | 生成模型密钥；缺失时服务可启动，但问答生成会失败 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 主模型名称 |
| `EMBEDDING_REMOTE_API_KEY` | 空 | 配置后优先使用 OpenAI 兼容的远程 Embedding |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | 本地 Embedding 模型；`.env.example` 使用 `Qwen/Qwen3-Embedding-0.6B` |
| `EMBEDDING_DIM` | `384` | 必须与模型输出维度一致（Qwen3-Embedding-0.6B 为 `1024`） |
| `EMBEDDING_DEVICE` | `cpu` | 本地 Embedding 设备；`.env.example` 为 Apple Silicon 填了 `mps` |
| `MINERU_API_KEY` | 空 | 配置后走 MinerU 云解析；否则本地 MinerU → pypdf 降级 |
| `MINERU_MODEL_VERSION` | `vlm` | 云解析版式模型：`vlm`（公式/行内公式更准，较慢）或 `pipeline` |
| `MINERU_MODEL_VERSION_FALLBACK` | `pipeline` | 主模型解析失败时的回退版本；置空表示不回退 |
| `JWT_SECRET_KEY` | 空 | 开发环境留空表示匿名访问；非开发环境必须配置 |
| `APP_ENV` | `development` | 非开发环境且未配置密钥时，服务拒绝启动 |
| `ARIADNE_DATA_DIR` | `backend/data` | 运行数据根目录（SQLite、原始 PDF、索引快照） |
| `ARIADNE_MODEL_DIR` | `backend/data/model_cache` | 模型缓存目录 |
| `ARIADNE_DB_PATH` | `<data>/ariadne.db` | SQLite 数据库路径 |
| `UPLOAD_MAX_BYTES` | `52428800`（50 MiB） | 单次上传大小上限 |
| `LLM_FALLBACK_ENABLED` | `false` | 开启后 DeepSeek 失败时降级到 fallback / Ollama |
| `RERANKER_ENABLED` | `true` | 是否启用检索结果重排 |

注意事项：

- 环境变量在导入期实例化，修改 `.env` 后需重启后端。
- `EMBEDDING_DIM` 与模型不一致会导致摄取失败；切换 Embedding 模型后必须重建已有文档索引，避免混用不同向量空间。
- 仅支持文本型 PDF；扫描版或纯图片型 PDF 会以 `PDF_TEXT_NOT_EXTRACTABLE` 失败。
- 完整字段、默认值与路径解析规则见 [docs/wiki/08-configuration.md](docs/wiki/08-configuration.md)。

## Docker 部署

```bash
docker compose -f docker-compose.app.yml up --build
```

| 服务 | 地址 |
|---|---|
| 前端 | <http://localhost:8080> |
| 后端 | <http://localhost:8000> |

- 容器通过 `env_file` 读取 `backend/.env`，启动前需先完成本地配置。
- `backend/data` 挂载到容器内 `/app/backend/data`，SQLite 与索引产物随宿主机持久化。
- 前端镜像使用 Nginx 反向代理后端，`/health` 可直接用于探活。
- `docker-compose.local-llm.yml` 用于本地 Ollama 评测，`docker-compose.test.yml` 用于 mock LLM 集成测试。

## API 概览

<!-- api-endpoints:start -->
| 方法 | 路径 | 说明 |
|---|---|---|
| DELETE | `/annotations/{annotation_id}` | Delete Annotation |
| PATCH | `/annotations/{annotation_id}` | Update Annotation |
| POST | `/auth/login` | 用用户名密码换取 JWT。 |
| GET | `/auth/me` | 返回当前 token 对应的用户。 |
| POST | `/auth/register` | 注册账号并直接签发 token。 |
| GET | `/collections` | List Collections |
| POST | `/collections` | Create Collection |
| PATCH | `/collections/{collection_id}` | Update Collection |
| POST | `/collections/{collection_id}/ask` | Ask Collection |
| POST | `/collections/{collection_id}/compare` | Compare Collection Papers |
| DELETE | `/collections/{collection_id}/papers/{paper_id}` | Remove Paper From Collection |
| PUT | `/collections/{collection_id}/papers/{paper_id}` | Add Paper To Collection |
| GET | `/digest` | Get Digest |
| GET | `/documents` | 跨会话的文献库列表（已归档会话不计入）。 |
| GET | `/features` | Get Features |
| GET | `/feed` | List Feed |
| POST | `/feed/refresh` | Refresh Feed |
| POST | `/feed/{item_id}/ignore` | Ignore Feed Item |
| POST | `/feed/{item_id}/save` | Save Feed Item |
| GET | `/health` | 健康检查：进程存活与后台任务线程状态。 |
| POST | `/integrations/notion/export` | Export Notion |
| POST | `/integrations/zotero/export` | Export Zotero |
| GET | `/notifications` | List Notifications |
| POST | `/notifications/check-citations` | 检查已收录论文的新引用；首次运行只记录基线。 |
| POST | `/notifications/check-versions` | 检查 arXiv 新版本；首次运行只记录基线。 |
| POST | `/notifications/deliver` | Deliver Notifications |
| POST | `/notifications/{notification_id}/read` | Mark Notification Read |
| GET | `/papers` | 文献库列表：按用户、状态、集合、标签与标题过滤。 |
| POST | `/papers` | 上传 PDF：创建论文、reading session、文档与摄取任务。 |
| GET | `/papers/export.bib` | Export Bibtex |
| GET | `/papers/export.csl.json` | Export Csl |
| GET | `/papers/export.md` | Export Markdown |
| POST | `/papers/import` | 按 arXiv / DOI / 链接导入：抓取元数据，有开放 PDF 时一并入库。 |
| GET | `/papers/reading-stats` | 阅读时长统计：按天与按论文聚合，默认最近 7 天。 |
| GET | `/papers/stats` | Get Library Stats |
| DELETE | `/papers/{paper_id}` | 硬删除论文及其会话、文档、批注、集合关联与磁盘产物。 |
| GET | `/papers/{paper_id}` | Get Paper |
| PATCH | `/papers/{paper_id}` | Update Paper |
| GET | `/papers/{paper_id}/annotations` | List Annotations |
| POST | `/papers/{paper_id}/annotations` | Create Annotation |
| POST | `/papers/{paper_id}/brief` | Generate Brief |
| GET | `/papers/{paper_id}/citations` | Get Citations |
| POST | `/papers/{paper_id}/explain` | Explain Selection |
| GET | `/papers/{paper_id}/glossary` | Generate Glossary |
| POST | `/papers/{paper_id}/reading-time` | 记录一次前台阅读时长（秒），累加到论文总时长与阅读日志。 |
| GET | `/review/weekly` | Get Weekly Review |
| PUT | `/review/weekly/note` | 保存本周复盘文字，返回更新后的周报。 |
| GET | `/sessions` | 按当前用户列出会话（不含已归档）。 |
| POST | `/sessions` | 新建空会话。 |
| DELETE | `/sessions/{session_id}` | 归档会话（幂等，不暴露会话是否存在）。 |
| GET | `/sessions/{session_id}` | 读取会话快照：文档、消息、任务与索引状态。 |
| PATCH | `/sessions/{session_id}` | 更新会话标题或置顶状态。 |
| POST | `/sessions/{session_id}/documents` | 上传 PDF 并受理异步摄取任务，立即返回 202。 |
| DELETE | `/sessions/{session_id}/documents/{document_id}` | 删除单篇文档（行 + 分块 + 磁盘产物）并重建会话索引。 |
| GET | `/sessions/{session_id}/documents/{document_id}/blocks/{block_id}/crop` | 返回正文块在原始 PDF 中的裁切图（公式/图片/复杂表格展示用）。 |
| GET | `/sessions/{session_id}/documents/{document_id}/chunks/{chunk_index}` | 把回答里的引用还原为原文段落，供前端阅读器定位。 |
| GET | `/sessions/{session_id}/documents/{document_id}/content` | 返回解析后的结构化正文，供阅读器渲染与引用定位。 |
| GET | `/sessions/{session_id}/documents/{document_id}/file` | 下载/内联渲染原始 PDF（前端阅读器用）。 |
| POST | `/sessions/{session_id}/index/rebuild` | 按当前用户的 Embedding 配置重建会话索引（同步）。 |
| POST | `/sessions/{session_id}/messages` | 发送提问，以 text/event-stream 流式返回回答。 |
| GET | `/sessions/{session_id}/runs/{run_id}` | 读取一次 Agent 运行的轨迹（run + steps）。 |
| GET | `/settings/alerts` | Get Alert Settings |
| PATCH | `/settings/alerts` | Update Alert Settings |
| GET | `/settings/models` | Get Model Settings |
| PATCH | `/settings/models` | Update Model Settings |
| GET | `/subscriptions` | List Subscriptions |
| POST | `/subscriptions` | Create Subscription |
| DELETE | `/subscriptions/{subscription_id}` | Delete Subscription |
<!-- api-endpoints:end -->

> 上表由 `contracts/openapi.json` 生成，请勿手改。更新契约后执行 `uv run --project backend python -m backend.scripts.api_table` 重新生成；完整字段与示例见 [docs/wiki/04-api.md](docs/wiki/04-api.md)。

## 开发与测试

### 后端

```bash
# 全部用例（缺少 torch / faiss 的用例自动 skip）
uv run --project backend pytest

# 按标记过滤
uv run --project backend pytest -m unit -v
uv run --project backend pytest -m integration -v

# Lint 与类型检查
uv run --project backend ruff check backend/src tests
uv run --project backend mypy --config-file backend/pyproject.toml \
  backend/src/backend/storage backend/src/backend/domain backend/src/backend/application
```

测试位于仓库根目录 `tests/`，按用途分层；用例数量以 `uv run --project backend pytest --collect-only -q` 的输出为准。

| 目录 | 覆盖内容 |
|---|---|
| `tests/unit/` | 领域模型、状态流转、仓储、适配器的隔离用例 |
| `tests/integration/` | 跨模块、存储与 API 边界用例 |
| `tests/architecture/` | 分层依赖与导入边界（AST 静态校验） |
| `tests/contracts/` | OpenAPI 快照、README 端点表、配置文档生成 |
| `tests/network/` | 需要外部网络、模型或 Docker，默认 skip |

### 前端

```bash
cd frontend
npm test          # Vitest
npm run lint      # ESLint
npm run typecheck # vue-tsc
npm run build     # 类型检查 + 生产构建
```

### 契约同步

修改后端请求/响应模型后，需要同步契约文件、端点表与前端类型：

```bash
uv run --project backend python -m backend.scripts.export_openapi
uv run --project backend python -m backend.scripts.api_table
cd frontend && npm run gen
```

### 集成测试脚本

以下脚本为 Bash 脚本，Windows 环境请使用 WSL 或 Git Bash：

```bash
# 使用 docker/mock-llm 验证 OpenAI 兼容 HTTP 链路，无需真实 Key
./scripts/run_mock_llm_tests.sh

# Docker Ollama + Qwen2.5-3B 本地模型评测
./scripts/run_local_llm_eval.sh

# Docker MailHog 验证 SMTP 实际投递
./scripts/run_smtp_test.sh
```

真实 arXiv 抓取冒烟测试默认 skip，需要显式开启：

```bash
ARIADNE_NETWORK_TESTS=1 uv run --project backend pytest \
  tests/network/test_arxiv_network.py tests/network/test_citations_network.py
```

### 持续集成

CI 定义在 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)：

| 任务 | 检查项 |
|---|---|
| 后端 | `ruff check` → `mypy` → `compileall` → `pytest -m "unit or integration"` |
| 前端 | `npm run lint` → `npm test` → 生成契约类型并 diff → `npm run build` |

### 发布前手工回归

- 启动日志打印实际加载的 `.env` 绝对路径；仓库根目录存在 `.env` 时打印 warning。
- 上传超过 50 MiB 的 PDF 返回 `413`，进程内存不随文件体积增长。
- 生成中断后重新生成，上一轮回答仍保留；SSE 空闲 15s 内出现 `: keep-alive` 帧。
- 登出后切换账号，不出现上一账号的会话、文档与消息。

## 离线评测

评测 CLI 与数据集格式见 [docs/wiki/09-evaluation.md](docs/wiki/09-evaluation.md)，依赖需通过 `uv sync --project backend --group eval` 安装。

从现有会话索引导出评测草稿：

```bash
uv run --project backend python -m ariadne_eval.cli generate-draft \
  --session-id session-example \
  --output data/evaluation/drafts/retrieval-v1-draft.jsonl \
  --max-samples 30
```

离线检索评测（默认不触发实时生成与 RAGAS）：

```bash
uv run --project backend python -m ariadne_eval.cli run \
  --dataset data/evaluation/reviewed/retrieval-v1.jsonl \
  --session-id session-example \
  --config-set retrieval-v1 \
  --output-dir eval_outputs/ragas \
  --run-name retrieval-exp-001
```

需要实时生成与 RAGAS 指标时，追加 `--with-generation --with-ragas`。生产模型评测与真实论文评测脚本：`scripts/run_real_paper_eval.py`、`scripts/run_full_pdf_eval.py`。

## 文档

| 文档 | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | 文档总索引与编写约定 |
| [docs/wiki](docs/wiki/README.md) | 工程事实基线：架构、数据模型、API、摄取与检索、配置、开发与排障 |
| [docs/analysis](docs/analysis/README.md) | 时点分析：审计、现状复核、能力缺口 |
| [docs/planning](docs/planning/README.md) | 产品规划、设计、功能清单与整改计划 |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | CI 流水线定义 |

## 已知限制

- 仅支持文本型 PDF，不处理扫描版或纯图片型 PDF。
- 检索按单会话、单 active snapshot 组织，暂不支持跨论文联合检索。
- 应用为单进程设计：任务队列、会话锁与向量库缓存均为进程内状态，不支持多副本部署。
- 问答质量依赖外部模型服务（DeepSeek 主用，可降级）与 Embedding 资源可用性。
- Agent 研究仅检索当前会话、只读不写，并受 `AGENT_MAX_STEPS` / `AGENT_MAX_TOOL_CALLS` / `AGENT_TIMEOUT_SECONDS` 预算约束；模型需支持工具调用。
- 前端交付范围为 PC Web，未适配移动端；部分输入区工具按钮仍为 UI 占位。
- 暂无可观测性指标（`/metrics`、tracing），仅有 stdout 日志。

## 贡献

1. 从 `main` 拉出功能分支，保持提交粒度清晰。
2. 遵循既有分层与命名约定，新增能力前先阅读 [docs/wiki/02-architecture.md](docs/wiki/02-architecture.md)。
3. 提交前至少通过相关 lint、类型检查与测试；涉及契约变更时同步更新 `contracts/`、README 端点表与前端类型。
4. 在 PR 描述中说明变更动机、影响范围与验证方式。

## License

本项目基于 [MIT License](LICENSE) 开源。
