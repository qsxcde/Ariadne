# 08 配置参考

定义：`backend/src/backend/config.py`（`RuntimeSettings`，pydantic-settings `BaseSettings`）
加载：`SettingsConfigDict(env_file=env_file_path(), extra="ignore")`，其中
`env_file_path() = backend_project_dir() / ".env"`
即：读取 **`backend/.env`**，未设置 `env_prefix`，环境变量名 = 字段名大写。
仓库根目录的 `.env` **不会被读取**，启动时会打印一条 warning。

```
Ariadne/backend/.env  ← 后端配置（唯一生效路径）
Ariadne/frontend/.env ← 仅 VITE_* 变量
```

启动日志会打印实际加载的路径：
`Configuration: loading /…/Ariadne/backend/.env`。

模块级单例 `settings = RuntimeSettings()` 在 import 时即完成加载；改配置必须重启进程。

## 1. 必填与校验

- `RuntimeSettings` 的 `deepseek_api_key` 为 `None`，**启动时不校验**。
- 真正需要生成时才调用 `require_generation_settings()`（`generation/llm.py` 首次取客户端时），缺失 `DEEPSEEK_API_KEY` 抛 `RuntimeError("DeepSeek generation requires DEEPSEEK_API_KEY to be configured.")`。
- 因此：可以只做上传/检索；一旦发起对话且缺 key，SSE 会返回 `error` 事件。

## 2. 全部配置项

### 2.1 LLM 生成

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | `None` | 主模型密钥；对话必需 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | OpenAI 兼容端点 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 主模型名 |

### 2.2 多模型降级

| 变量 | 默认 | 说明 |
|---|---|---|
| `LLM_FALLBACK_ENABLED` | `False` | 总开关，同时控制 fallback 与 ollama |
| `FALLBACK_API_KEY` | `None` | 备用 provider 密钥 |
| `FALLBACK_BASE_URL` | `None` | 为空则不启用备用 provider |
| `FALLBACK_MODEL` | `glm-4-flash` | |
| `OLLAMA_BASE_URL` | `None` | 为空则不启用 Ollama |
| `LLM_MAX_TOKENS` | `3072` | 单次生成的最大 token 上限；推理模型会先消耗 reasoning 预算 |
| `LLM_CONTEXT_CHARS` | `24000` | 提示词上下文预算（字符）；本地小上下文模型可调低，首个命中块优先保留 |
| `MODEL_SETTINGS_ENCRYPTION_KEY` | `None` | 用户模型 API Key 的落库加密密钥；未设置时回退 `JWT_SECRET_KEY` |
| `OLLAMA_MODEL` | `qwen2.5:7b` | |

### 2.3 Embedding

| 变量 | 默认 | 说明 |
|---|---|---|
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | 本地模型仓库 ID |
| `EMBEDDING_MODEL_SOURCE` | `modelscope` | `modelscope` 或 `huggingface` |
| `EMBEDDING_AUTO_DOWNLOAD` | `True` | 本地无权重时是否下载 |
| `EMBEDDING_LOCAL_FILES_ONLY` | `True` | 传给 SentenceTransformer |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` / `cuda` / `mps` |
| `EMBEDDING_DIM` | `384` | **决定 FAISS 索引维度**，换模型必须同步 |
| `EMBEDDING_REMOTE_API_KEY` | `None` | 配置后远程优先 |
| `EMBEDDING_REMOTE_MODEL` | `Qwen/Qwen3-VL-Embedding-8B` | |
| `EMBEDDING_REMOTE_BASE_URL` | `https://api.siliconflow.cn/v1` | |

> 设置页的个人 Embedding 配置优先于 env；可选模型列表由 `EMBEDDING_REMOTE_MODEL` 生成。
> 索引指纹（`mode|provider|model|dim`）变化后，旧索引会提示重建；仅更换 API Key 不会触发重建。

### 2.4 分块与上传

| 变量 | 默认 | 说明 |
|---|---|---|
| `MAX_CHUNK_TOKENS` | `800` | 估算 token 上限（非真实 tokenizer） |
| `CHUNK_OVERLAP_TOKENS` | `100` | 重叠按**字符**截取 |
| `UPLOAD_MAX_BYTES` | `52428800` | 50 MiB |

### 2.5 存储路径

| 变量 | 默认 | 说明 |
|---|---|---|
| `ARIADNE_DATA_DIR` | `None` → `backend/data` | 运行时数据根 |
| `ARIADNE_MODEL_DIR` | `None` → `<数据根>/model_cache` | 模型缓存根 |
| `ARIADNE_DB_PATH` | `None` → `<数据根>/ariadne.db` → `backend/src/backend/storage/sqlite/ariadne.db` | SQLite 文件 |

### 2.6 MinerU

| 变量 | 默认 | 说明 |
|---|---|---|
| `MINERU_API_KEY` | `None` | 配置后启用云解析（优先级最高） |
| `MINERU_API_BASE_URL` | `https://mineru.net` | |
| `MINERU_API_TIMEOUT` | `300` | 单次 HTTP 请求超时（秒） |
| `MINERU_API_POLL_INTERVAL` | `2.0` | 首次轮询间隔（秒） |
| `MINERU_API_POLL_MAX_INTERVAL` | `10.0` | 轮询退避上限（秒） |
| `MINERU_API_MAX_POLL_TIME` | `600` | 单批次总等待上限（秒） |
| `MINERU_API_MAX_RETRIES` | `3` | 429/5xx/网络错误重试次数 |
| `MINERU_API_RETRY_BASE_DELAY` | `1.0` | 指数退避基数（秒） |
| `MINERU_API_RETRY_MAX_DELAY` | `30.0` | 单次重试等待上限（秒） |
| `MINERU_API_IS_OCR` | `False` | 云 API `files[].is_ocr`；本地 OCR 用 `MINERU_DISABLE_OCR` |
| `MINERU_API_PAGE_RANGES` | `None` | 云 API 页范围，如 `1-50`；为空表示全部 |
| `MINERU_MODEL_VERSION` | `vlm` | `pipeline` / `vlm` / `MinerU-HTML` |
| `MINERU_MODEL_VERSION_FALLBACK` | `pipeline` | 主模型失败时的回退版本；空字符串表示不回退 |
| `MINERU_LANGUAGE` | `ch` | 云 API 文档语言 |
| `MINERU_REQUIRE_CLOUD` | `False` | 为 `True` 时云解析失败不再降级到本地/pypdf |
| `MINERU_TORCH_DEVICE` | `cpu` | 本地 CLI 设备 |
| `MINERU_DISABLE_OCR` | `True` | 仅本地 MinerU |
| `MINERU_TABLE_ENABLE` | `True` | 云端/本地表格识别 |
| `MINERU_FORMULA_ENABLE` | `True` | 云端/本地公式识别 |
| `MINERU_SHOW_DOWNLOAD_PROGRESS` | `False` | 本地子进程输出透传 |

### 2.7 索引与任务轮询

| 变量 | 默认 | 说明 |
|---|---|---|
| `INDEX_POLL_INTERVAL` | `0.05` | 对话等待索引的初始间隔 |
| `INDEX_POLL_MAX_INTERVAL` | `1.0` | 退避上限 |
| `INDEX_MAX_WAIT` | `10.0` | 总等待预算（秒） |
| `RUNNER_IDLE_POLL_INTERVAL` | `0.05` | runner 空转间隔 |
| `RUNNER_CONCURRENCY` | `2` | 摄取作业并发数；1 为串行（旧行为） |

### 2.8 检索

| 变量 | 默认 | 说明 |
|---|---|---|
| `RETRIEVAL_TOP_K` | `5` | 仅纯 dense 分支使用 |
| `SOURCE_EXCERPT_MAX_CHARS` | `220` | `SourceRef.text_excerpt` 截断长度 |
| `MAX_EXPANDED_CHUNKS` | `8` | 上下文块数上限 |
| `SAME_SECTION_WINDOW` | `1` | 同章节邻居窗口 |
| `ADJACENT_WINDOW` | `1` | 相邻 chunk 窗口 |
| `BM25_TOP_K` | `8` | |
| `DENSE_TOP_K` | `8` | 设 0 即关闭 dense |
| `SEED_TOP_K` | `8` | RRF 后保留数 |
| `RRF_K` | `60` | |
| `INCLUDE_LINKED_BLOCKS` | `False` | 是否带入 caption 关联块 |

### 2.9 Reranker

| 变量 | 默认 | 说明 |
|---|---|---|
| `RERANKER_ENABLED` | `True` | 关掉即跳过重排 |
| `RERANKER_MODEL_ID` | `BAAI/bge-reranker-v2-m3` | 本地模型 |
| `RERANKER_DEVICE` | `cpu` | |
| `RERANKER_AUTO_DOWNLOAD` | `True` | |
| `RERANKER_MAX_LENGTH` | `1024` | |
| `RERANK_TOP_K` | `8` | |
| `RERANKER_REMOTE_ENABLED` | `True` | 需同时配置 `EMBEDDING_REMOTE_API_KEY` |
| `RERANKER_REMOTE_MODEL` | `BAAI/bge-reranker-v2-m3` | |
| `RERANKER_REMOTE_BASE_URL` | `https://api.siliconflow.cn/v1` | |

> 设置页的个人重排配置优先于 env；重排只影响检索排序，修改后立即生效，无需重建索引。

### 2.10 查询改写与术语扩展

| 变量 | 默认 | 说明 |
|---|---|---|
| `HISTORY_REWRITE_ENABLED` | `True` | |
| `HISTORY_REWRITE_MAX_ROUNDS` | `4` | 参与改写的最近轮数 |
| `HISTORY_REWRITE_MIN_QUERY_LENGTH` | `3` | 短查询强制改写 |
| `TERM_EXPAND_ENABLED` | `True` | |
| `TERM_EXPAND_GLOSSARY_PATH` | `backend/data/term_glossary.json` | **相对当前工作目录** |
| `TERM_EXPAND_LLM_FALLBACK` | `True` | 词表未命中时调 LLM |

### 2.11 鉴权

| 变量 | 默认 | 说明 |
|---|---|---|
| `JWT_SECRET_KEY` | `""` | 为空且 `APP_ENV` 为开发类取值 = 匿名旁路（数据接口免鉴权、auth 接口 400）；生产环境必须设置 |
| `JWT_ALGORITHM` | `HS256` | |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 天 |

### 2.12 通知投递（SMTP）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SMTP_HOST` | `None` | SMTP 服务器；为空时邮件投递不可用 |
| `SMTP_PORT` | `587` | SMTP 端口 |
| `SMTP_USERNAME` | `None` | 登录名；为空则匿名发送 |
| `SMTP_PASSWORD` | `None` | 登录密码 |
| `SMTP_FROM` | `None` | 发件人地址；邮件投递必填 |
| `SMTP_STARTTLS` | `True` | 是否使用 STARTTLS |

Webhook 投递不需要这些配置；`POST /notifications/deliver` 可传 `webhook_url` 或 `email_to`。

### 2.13 应用与文案

| 变量 | 默认 | 说明 |
|---|---|---|
| `APP_ENV` | `development` | 决定是否允许匿名旁路：`development/dev/local/test/testing` 允许；其它值（如 `production`）在缺 `JWT_SECRET_KEY` 时对数据接口返回 503 |
| `CORS_ORIGIN_REGEX` | `http://(localhost\|127\.0\.0\.1):\d+` | 前端跨域 |
| `MSG_INDEX_NOT_READY` | `论文仍在处理中，请稍后重试。` | 索引超时提示 |
| `MSG_INDEX_EMBEDDING_STALE` | `Embedding 模型已变更，当前索引需要重建后才能检索。` | 索引与当前 Embedding 配置不匹配时的提示 |
| `MSG_EMPTY_RETRIEVAL` | `未在当前检索结果中找到可支持该问题的论文依据。` | 检索为空提示 |
| `MSG_NO_VALID_CITATIONS` | `模型生成的回答中未引用有效论文来源，请核实。` | 引用校验 warning |
| `MSG_DEFAULT_SESSION_TITLE` | `新论文会话` | 默认标题，同时是"是否自动改名"的哨兵值 |

### 2.14 Agent（P0）

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_ENABLED` | `True` | Agent 模式总开关；关闭后前端只保留快速问答 |
| `AGENT_MAX_STEPS` | `6` | 单个 run 的最大图步数，同时决定 recursion limit |
| `AGENT_MAX_TOOL_CALLS` | `6` | 单个 run 允许的工具调用次数预算 |
| `AGENT_TIMEOUT_SECONDS` | `120` | 单次模型调用与 run 预算的超时时间（秒） |
| `AGENT_TOOL_PREVIEW_CHARS` | `300` | 工具结果返回给模型的单片段预览字符数 |
| `AGENT_MAX_EVIDENCE_CHARS` | `12000` | 工具结果与最终回答可使用的证据总字符上限 |
| `AGENT_MAX_HISTORY_TURNS` | `6` | Agent 带入的历史轮数，超出部分丢弃 |

## 3. 路径解析

```
backend_root()  = backend/src/backend
project_root()  = 仓库根（.env 位置）

data_dir()      = ARIADNE_DATA_DIR or backend_root().parent / "data"   → backend/data
model_dir()     = ARIADNE_MODEL_DIR or data_dir()/model_cache
mineru_model_dir()           = model_dir()/mineru
mineru_modelscope_cache_dir()= model_dir()/mineru/modelscope
embedding_model_dir()        = model_dir()/embeddings/<EMBEDDING_MODEL 末段名>

DB: ARIADNE_DB_PATH → data_dir()/ariadne.db → backend/src/backend/storage/sqlite/ariadne.db
Agent checkpoints: data_dir()/agent/checkpoints.sqlite（独立于应用库）
```

三者都会 `mkdir(parents=True, exist_ok=True)`，目录不存在会自动创建。

## 4. 示例 `.env`

```env
# 必填：对话生成
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-v4-flash

# 可选：远程 embedding（配置后优先于本地）
# EMBEDDING_REMOTE_API_KEY=sk-yyyy
# EMBEDDING_REMOTE_MODEL=Qwen/Qwen3-VL-Embedding-8B

# 本地 embedding
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_MODEL_SOURCE=modelscope
EMBEDDING_DEVICE=cpu
EMBEDDING_DIM=384

# 解析
MINERU_TORCH_DEVICE=cpu
MINERU_DISABLE_OCR=true

# 存储
# ARIADNE_DATA_DIR=/var/lib/ariadne
# ARIADNE_DB_PATH=/var/lib/ariadne/ariadne.db

# 鉴权（留空 = 开发旁路）
# JWT_SECRET_KEY=change-me

# 多模型降级
# LLM_FALLBACK_ENABLED=true
# FALLBACK_API_KEY=sk-zzzz
# FALLBACK_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# FALLBACK_MODEL=glm-4-flash
```

## 5. 改配置时的注意事项

1. **`EMBEDDING_DIM` 必须与模型输出维度一致**，否则追加索引时抛 `ValueError("Embedding dimension mismatch")`；换模型后需对已有文档重建索引。
2. **切换 embedding 空间等于让旧索引失效**，历史会话的 FAISS 快照仍指向旧向量空间，检索结果不可比。
3. `TERM_EXPAND_GLOSSARY_PATH` 是相对路径，按进程工作目录解析；用 `uv run --project backend ...` 时工作目录是仓库根，因此默认可命中 `backend/data/term_glossary.json`。
4. 生产必须显式设置 `ARIADNE_DB_PATH` 或 `ARIADNE_DATA_DIR`，否则默认 DB 会落进源码包目录。
5. 生产必须设置 `JWT_SECRET_KEY`，否则任何人可匿名读写全部会话（且归属校验缺失）。
