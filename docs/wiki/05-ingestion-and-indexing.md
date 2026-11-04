# 05 文档摄取与索引

覆盖"上传 PDF → 可检索"的完整链路。相关代码：

- 落盘与建行：`backend/src/backend/application/ingestion/documents.py`
- 调度：`backend/src/backend/worker/runner.py`
- 状态机与产物：`backend/src/backend/application/ingestion/job.py`
- 解析与切块：`backend/src/backend/rag/ingestion/`；具体解析器在 `backend/src/backend/adapters/parsers/`
- 索引提交：`backend/src/backend/application/ingestion/indexing.py`、`backend/src/backend/adapters/vector/faiss_store.py`

## 1. 阶段总览

```
① 上传（请求线程，同步）
   documents(uploaded) + jobs(queued) + PDF 落盘                        → 202

② 调度（runner 线程）
   tick → 取 1 条 queued job → CAS 置 running(attempt+1) → 加会话锁

③ 解析（parsing）
   process_pdf_document：解析器链 → RawParserResult → DocumentIR → chunks

④ 产物落盘 + 元数据回写（parsed）
   document.ir.json / document.md / document.normalized.md / quality_report.json

⑤ 切块入库（chunked）
   delete_chunks_for_document + insert_chunks（同事务重算 chunk_count）

⑥ 建索引（indexing）
   取目标 chunks → 过滤参考文献 → 追加到上一 ready 快照 → 写候选文件

⑦ 提交（ready）
   快照 building → ready；旧 ready → stale；upsert retrieval_indexes；文档 ready
```

任一阶段抛异常 → `_mark_failed`：快照 `failed`、删 chunks、清产物字段与目录、`discard_store`、文档 `failed`、`job failed`。

## 2. 上传落地

`documents.intake_document_upload`：

1. `_validate_upload`：`file_size` 为 `None` → 400；超过 `upload_max_bytes`（默认 50 MiB）→ 413；前 4 字节不是 `%PDF` → 400。路由传入的是 `file.size`，为空时退化为 `len(pdf_bytes)`。
2. `paths.session_upload_key` → `raw/<session_id>/<document_id>.pdf`，经 `object_store.put_bytes` 落地；local 后端返回绝对路径，s3 后端返回对象 key。
3. `documents.create_document`：硬编码 `status="uploaded"`、`chunk_count=0`、`error_message=NULL`。
4. `jobs.create_job`：`type="document_ingestion"`、`status="queued"`、`stage="uploaded"`、`payload_json={document_id, filename, file_path}`、`attempt=0`。
5. `sessions.touch_session`。
6. 若会话标题仍是 `settings.msg_default_session_title`，改为文件名。

写存储与建行不在同一事务中，但有显式补偿：`create_document` 或 `create_job` 抛错时，`delete_document` + 删除已写入对象后再抛出。`touch_session` 与"标题自动改名"在 `try` 之外，且用 `suppress` 包裹，失败只影响排序/标题，不影响上传结果。

## 3. 任务调度

`InProcessJobRunner`（`worker/runner.py`）：

| 行为 | 实现 |
|---|---|
| 线程 | daemon 线程 `ariadne-job-runner`，`runner_idle_poll_interval=0.05s` 空转 |
| 取任务 | `list_runnable_jobs(limit=1)`：`status='queued' ORDER BY created_at ASC` |
| 领取 | `mark_job_running` CAS：`WHERE id=? AND status='queued'`，`attempt+1`，清 `error_message`，置 `started_at` |
| 串行 | 每 `session_id` 一把 `threading.Lock`，同会话任务不并发 |
| 分发 | `worker/runner.py` 按 `jobs.type` 查 handler 注册表；未注册的类型直接失败，新增任务类型不需要改 runner |
| 执行 | `worker/handlers.ingest_document`：要求 `stage=uploaded`；读 `payload_json` → 读 PDF 字节 → `application.ingestion.run_document_ingestion_job`；若 payload 含 `mineru_batch_id` 则先查询该批次，命中即复用结果，避免重复提交计费 |
| 收尾 | 成功 `mark_job_finished("succeeded")`；异常 `mark_job_finished("failed", str(exc))` |
| 恢复 | 启动时 `recover_interrupted_jobs`：`running` / `interrupted` → `queued`，清时间戳与错误；MinerU 批次号保留在 payload 中供续跑 |

单线程 + 单条领取意味着多文档上传是**排队**处理，吞吐取决于单个 PDF 的解析耗时。

## 4. 解析器链

`composition/parser_chain()` 构建候选链，`rag/ingestion/pipeline.py` 按顺序尝试，第一个成功即返回：

```
[mineru_api（仅当配置 MINERU_API_KEY）] → mineru（本地 CLI） → text_pdf（pypdf 兜底）
```

全部失败 → `PaperParseError`，错误信息聚合每个后端的失败原因；成功降级时把原因写入 `metadata["fallback_reason"]`，最终进入 `QualityReport.fallback_reason` 并追加 `PARSER_FALLBACK: ...` warning。
配置 `MINERU_REQUIRE_CLOUD=true` 且云解析失败时直接抛错，不再静默降级。
传 `parser_backend=` 参数时只使用指定后端（测试/评测用）。

`ParserBackend` 协议（`domain/parsing.py`），具体实现在 `adapters/parsers/`：

```python
class ParserBackend(Protocol):
    name: str
    version: str
    def parse(self, pdf_bytes: bytes, filename: str | None = None) -> RawParserResult: ...

class RawParserResult(BaseModel):
    markdown: str
    page_count: int
    pages: list[dict] = []
    metadata: dict = {}
    source_parser: str | None = None
    warnings: list[str] = []
    bbox_unit: BBoxUnit = "points"   # points | normalized_1000 | normalized_1
```

| 后端 | name / version | 布局信息 | 关键行为与限制 |
|---|---|---|---|
| `MinerUApiBackend` | `mineru_api` / `1.2` | 有（按页分组 blocks） | MinerU 云 API v4：`POST file-urls/batch` 申请签名 URL → 无鉴权 `PUT` 上传 → 轮询 `extract-results/batch/{batch_id}` → 下载结果 ZIP；单文件 ≤ 200 MiB；`data_id` 由 document id / PDF SHA-256 生成，`batch_id` 持久化到 job payload，任务恢复时先查询已有批次避免重复提交；`model_version`（`pipeline`/`vlm`/`MinerU-HTML`）、`language`、`is_ocr`、`page_ranges`、formula/table 均由配置控制；结果优先级 `*_content_list_v2.json` → `*_content_list.json` → `content.json`；table 块拼接 `table_caption + table_body + table_footnote`，`image/chart` 保留为图块并标记 `has_image`（有 caption 时文本为 caption，无 caption 也保留供阅读器裁切）；`content_list` 的 bbox 按 0–1000 归一化上报（`bbox_unit="normalized_1000"`） |
| `MinerUBackend` | `mineru` / `unknown` | 无（`pages=[]`，只有 `full.md`） | 子进程 `mineru -p ... -o ... -b pipeline`，超时硬编码 600s；模型缓存不完整直接抛错；注入 `MINERU_MODEL_HOME/SOURCE/DEVICE_MODE/MODELSCOPE_CACHE/TABLE/FORMULA/DISABLE_OCR`；`mps` 失败且错误含 mps/metal 时自动重试一次 `cpu` |
| `TextPDFBackend` | `pypdf-text` / `unknown` | 有（整页单栏） | `pypdf` 抽文本，空页跳过；跨页重复行按页眉页脚丢弃，页码行跳过；每页按词数切块 `clamp(max_chunk_tokens//3, 80~180)`；用编号 / 罗马数字 / 章节关键词 / 全大写短行保守恢复 `title`（带 `heading_level`），其余为 `paragraph`；bbox 为整页、`confidence=0.5`（标题 0.6）；加密 PDF 抛 `RuntimeError` |

## 5. 归一化（`normalizer.py`）

输入 `RawParserResult`，输出 `DocumentIR`：

0. bbox 归一化：按 `bbox_unit` 统一到 `normalized_1`——`points` 保留原值；`normalized_1000` 的 bbox 除以 1000 且页宽高置 1.0；`normalized_1` 页宽高置 1.0。页眉页脚检测与阅读顺序均基于归一化后的页面。
1. 扫描页边缘重复文本 → 判为页眉页脚（同一文本出现在 ≥2 页的页边区域）。
2. 逐页阅读顺序排序：双栏检测（≥4 块、左右各 ≥2 块、左列最右 < 右列最左，列缝 > 页宽 5%）→ 栏内按 `(y0, x0)`。
3. 丢弃空文本块（`formula` / `figure` 例外）；空文本且 bbox 全 0 的块告警跳过。
4. 类型判定：解析器已给合法类型则沿用，否则走 `detect_block_type` 启发式；文本做 `sanitize_extracted_text` 清洗，非公式块用 `wrap_bare_latex` 补齐行内公式分隔符。
5. 视觉块（`image/figure/picture`）：带 `has_image` 的保留为 `figure`，其余纯视觉块丢弃。
6. 标题（`title` / `heading`）→ 优先用解析器上报的 `heading_level` 更新 `section_path`，缺失时回退编号启发式，并 `clean_heading` 去编号；维护 `in_references` 状态（`references` 开启，appendix/supplementary/acknowledgments 关闭）；`reference` 块强制 `section_path=["References"]`。
7. 生成 `BlockIR`：`id = f"p{page_number}-ro{reading_order}"`，`reading_order` 全文档单调递增。
8. 页内 `attach_caption_links`：caption → 最近的 table/figure，`relation="caption_for"`。
9. 汇总 `outline`（heading 文本序列）与 `QualityReport`。

### 块类型启发式（`block_classifier.py`）

| 规则 | 判定 |
|---|---|
| 纯数字 + 位于页边距 | `header_footer` |
| 跨页重复 + 位于页边距 | `header_footer` |
| 命中 `HEADING_PATTERN`（abstract/introduction/conclusion/references/数字编号）且 ≤12 词 | `heading` |
| 参考文献区内 `^\[\d+\]` | `reference` |
| 含 `fig./figure/图` | `figure_caption` |
| 含 `table/表` | `table_caption` |
| 以 `\|` 开头且 `\|` ≥ 2 个 | `table` |
| ≤12 词且含 ≥2 个数学符号 | `formula` |
| 其它 | `paragraph` |

默认置信度：`header_footer 0.99`；`heading/reference/figure_caption/table_caption/table 0.93`；`paragraph 0.9`；`formula 0.7`（空文本 0.3）；`unknown 0.4`。
页边距阈值：`y1 ≤ 0.1H` 或 `y0 ≥ 0.9H`。

## 6. 质量报告（`quality_reporter.py`）

| 指标 | 计算 |
|---|---|
| `text_block_count` | `type == paragraph` 数 |
| `heading_count` | `type in {heading, title}` 数 |
| `low_confidence_block_count` | `confidence < 0.5` 数 |
| `filtered_header_footer_count` | `header_footer` 块数（不参与切块） |
| 其它计数 | table / figure_caption / table_caption / formula |

`overall_status` 判定：

- 无 blocks 且无 heading → `failed`
- 无 blocks 或 `heading_count == 0` → `poor`
- 否则 `good`；若同时存在 warning → `usable_with_warnings`

warning 例：`NO_HEADINGS_DETECTED`、`LOW_TEXT_DENSITY`、`PARSER_FALLBACK: <原因>`。
解析器降级原因同时存入 `QualityReport.fallback_reason`；归一化后的坐标单位写入 `DocumentIR.bbox_unit`（随 parsed IR JSON 落盘），供 `application/documents._resolve_block_boxes` 还原为 0–1 坐标。

结果随文档落库为 `parse_quality_status`，并写入 `quality_report.json`。

## 7. 切块（`chunking.py`）

流程：

1. 跳过 `title / heading / header_footer / figure`（图块不进入检索文本）。
2. 代码块（以 ` ``` ` 开头）单独成块；`reference` 单独成块。
3. 可合并类型 `{paragraph, figure_caption, table_caption, reference}` 进缓冲区，`section_path` 变化时 flush。
4. 其它类型 flush 后单独成块。
5. 超限时用 `RecursiveCharacterTextSplitter` 按分隔符递归切分，所有长度均按 **token 估算** 计。

单位与参数：

- 实际传入 `max_tokens = settings.max_chunk_tokens(800)`、`overlap_tokens = settings.chunk_overlap_tokens(100)`。
- `DEFAULT_MAX_TOKENS=2000` / `DEFAULT_OVERLAP_TOKENS=120` 仅在未传参时生效。
- token 估算：`token_units` 以 12 units = 1 token，ASCII 3 units/char（约 4 字符/token）、CJK 8 units/char（约 1.5 字符/token）；`estimate_tokens` 返回整数 token，不是真实 tokenizer 计数。
- 分隔符 `["\n\n", "\n", ". ", "。", "！", "？", " ", ""]`。

渲染与预算：

- 块渲染统一走 `rag/ingestion/render.py::render_block`，chunk 正文与导出 Markdown 不再各写一套；`ordered_blocks` 同样由该模块提供。
- 切块完成后 `application/ingestion._log_chunk_budget` 记录 `avg/max_est_tokens` 与 `max_chars`；当 `max_chars > MAX_EMBEDDING_CHARS(1600)` 时打 WARNING，提示 embedding 会截断尾部（此前是静默截断）。

`Chunk` 元数据填充规则：

| 字段 | 规则 |
|---|---|
| `text` | `"{heading_prefix}\n\n{body}"`，`section_path` 逐级生成 `##`…`######` |
| `section` | `" > ".join(section_path)` |
| `chunk_index` | 同文档内全局自增 |
| `type` | 合块时降级为 `paragraph`，代码块为 `code`，其余保留主类型 |
| `page_start/page_end` | 合块取 min/max；markdown 兜底为 `None` |
| `bbox` | 合块取并集；兜底 `None` |
| `block_ids` / `block_types` | 合块 id 列表 / 去重类型；兜底 `[]` / `["markdown"]` |
| `linked_block_ids` | `links` 目标 id 去重；无则 `None` |
| `confidence` | 合块取 **min**；兜底 `0.5` |

两级降级：IR 切不出块 → 用原始 markdown 重切（`type="markdown"` 兜底块）；仍为空 → 用首个标题造单块（`section="Abstract"`, `confidence=0.3`, page 1-1）；再失败 → `PaperParseError("NO_RETRIEVABLE_CHUNKS: ...")`。

## 8. 产物文件

`save_ingestion_artifacts(artifact_prefix=...)` 通过对象存储写入 `raw/<session_id>/parsed/<document_id>/`：

| 文件 | 内容 |
|---|---|
| `document.ir.json` | `DocumentIR.model_dump(mode="json")`，`sort_keys=True, indent=2` |
| `document.md` | 原始解析 markdown（为空则退化为 normalized） |
| `document.normalized.md` | `export_markdown(DocumentIR)` 结果，跳过 `header_footer` |
| `quality_report.json` | `QualityReport` JSON |

前三个中的 IR / markdown / quality 报告引用回写到 `documents` 表；`document.normalized.md` 只落盘不入库。阅读器裁切图缓存也写入同一前缀的 `crops/`。

## 9. 索引构建与提交

### 9.1 候选快照

`indexing.build_candidate_snapshot`：

1. `uuid4()` 生成 token，`create_building_snapshot` 写 `index_snapshots(status=building, document_ids_json=[...], embedding_fingerprint, embedding_model)`。
2. 取目标 chunks（当前会话全部可索引块），`filter_indexable_chunks` 剔除参考文献块。
3. 增量构建：若存在 previous ready 快照且 Embedding 指纹一致，`FAISSVectorStore.load(prev)` 后只追加"不在 `document_ids` 中"的新文档块；指纹不一致时丢弃旧快照、全量重建，避免混合不同模型的向量。
4. `FAISSVectorStore.save` 先写临时文件，再由 `object_store.put_file` 上传/复制到 `index/<sid>/snapshots/`；失败 → `SnapshotCommitError(candidate_snapshot=..., preserve_candidate_snapshot_files=False)`。

关键语义：**快照是整会话累积索引**，不是单文档索引。新文档 = 旧 ready 快照 + 新块；Embedding 变化 = 全量重建。

### 9.2 提交

`indexing.commit_ready_snapshot`：

```
校验：快照存在、session 匹配、document_id ∈ snapshot.document_ids
  → mark_snapshot_ready
        同事务：同会话其它 ready → stale；目标 building → ready
  → upsert retrieval_indexes(status=ready, 指向新路径)
  → documents.update_document_status(ready, chunk_count)
  → registry.discard_store(session_id)
```

### 9.3 回滚

任何一步失败：

1. `rollback_snapshot_promotion`：旧 `stale → ready`，新快照 `ready → failed`（写 `error_message`）。
2. 若 `retrieval_indexes` 已发布，恢复旧行；无旧行则写 `status='failed'`。
3. `discard_store` 清缓存。

`SnapshotCommitError.preserve_candidate_snapshot_files=True` 时保留候选文件以便排查，否则删除。

### 9.4 读取侧

`registry.get_store` 优先读 `retrieval_indexes`（legacy），其次 active ready 快照，再次从 `chunks` 内存重建，最后空 store。详见 [03 数据模型与存储](03-data-model.md) 第 6 节。

检索前会比较快照的 `embedding_fingerprint` 与当前用户的 Embedding runtime（`mode|provider|model|dim`）；不一致时抛 `IndexEmbeddingMismatchError`，前端阅读页显示「重建索引」。历史 NULL 指纹按 env 配置（v17 之前的行为）比较。重建入口：`POST /sessions/{session_id}/index/rebuild`。

## 10. 失败清理

`ingestion._mark_failed` 统一处理：

1. 若存在候选快照 → `mark_snapshot_failed`，按 `preserve_candidate_snapshot_files` 决定是否删文件。
2. `delete_chunks_for_document`（`chunk_count` 归零）。
3. 清空 `documents` 的 `parsed_ir_path` / `parsed_markdown_path` / `quality_report_path` / `parser_name` / `parser_version` / `parse_quality_status`。
4. 校验路径安全后删除 `parsed/<document_id>` 目录（`_is_safe_parsed_artifact_dir` 双重校验）。
5. `registry.discard_store`。
6. `update_document_status(failed, error=str(exc))`。

原始 PDF 保留（便于人工排查）。

## 11. 关键参数

| 参数 | 默认 | 位置 |
|---|---|---|
| `upload_max_bytes` | 52428800（50 MiB） | `config.py` |
| `max_chunk_tokens` | 800 | `config.py` → `ingestion/pipeline.py` |
| `chunk_overlap_tokens` | 100 | 同上 |
| `mineru_torch_device` | `cpu` | `config.py` |
| `mineru_disable_ocr` | `True` | 同上 |
| `mineru_table_enable` / `mineru_formula_enable` | `True` / `True` | 同上 |
| `mineru_api_key` | `None`（为空则不启用云解析） | 同上 |
| `mineru_api_timeout` / `mineru_api_poll_interval` / `mineru_api_max_poll_time` | 300 / 2.0 / 600 | 同上 |
| `mineru_api_poll_max_interval` | 10.0（轮询退避上限） | 同上 |
| `mineru_api_max_retries` / `mineru_api_retry_base_delay` / `mineru_api_retry_max_delay` | 3 / 1.0 / 30.0 | 同上 |
| `mineru_model_version` | `vlm`（可选 `pipeline` / `MinerU-HTML`） | 同上 |
| `mineru_model_version_fallback` | `pipeline`（空字符串关闭回退） | 主版本解析失败后重提一次，鉴权失败不回退 |
| `mineru_language` | `ch` | 同上 |
| `mineru_api_is_ocr` / `mineru_api_page_ranges` | `False` / `None` | 同上 |
| `mineru_require_cloud` | `False`（true 时云解析失败不降级） | 同上 |
| `runner_idle_poll_interval` | 0.05 | 同上 |
| MinerU 本地子进程超时 | 600s（硬编码） | `ingestion/mineru_backend.py` |
| MinerU API 单文件上限 | 200 MiB（硬编码） | `ingestion/mineru_api_backend.py` |
| 低置信阈值 | 0.5（硬编码） | `ingestion/quality_reporter.py` |

## 12. 扩展点

**新增解析后端**：

1. 在 `adapters/parsers/` 实现 `ParserBackend`（`name`、`version`、`parse`）。
2. 在 `composition.parser_chain()` 中按优先级插入。
3. 若后端不返回 `pages`，只靠 `markdown` 也能工作（会走 markdown 兜底切块）。

**调整切块策略**：改 `chunking.py` 的 `MERGEABLE_TYPES` / `SEPARATORS` / token 估算；若改单位语义，需同步 `settings.max_chunk_tokens` 的注释与评测预期。

**改变索引可见性**：不要绕过 `commit_ready_snapshot` 直接写 `index_snapshots.status`，否则 `retrieval_indexes` 与文档状态会与实际不一致（这正是回滚逻辑存在的原因）。
