# RAG 策略判断（2026-11-02）

> 问题：Native RAG 是否足够？是否需要引入更复杂的 RAG？
> 结论：**对 M0/M1 的单篇阅读与问答，当前「工程化 RAG」已经足够；对 M2 的跨论文对比，单索引 RAG 不够；但不建议现在上 GraphRAG 或自主 Agent。**
> 关联：[产品规划](../planning/product-plan-2026-11-02.md)、[M0 设计稿](../planning/m0-paper-model-2026-11-02.md)、[检索与问答](../wiki/06-retrieval-and-chat.md)

## 0. 先定义清楚

「Native RAG」通常指最朴素的一条链：

~~~text
query → embedding → top-k 向量检索 → 拼进 prompt → LLM 生成
~~~

而 Ariadne 现在并不是这个形态，已经属于「工程化 RAG」：

| 能力 | 当前实现 | 位置 |
|---|---|---|
| 章节感知切块 | 按 section / 类型 / 页码切块 | `rag/ingestion/chunking.py:24` |
| 混合召回 | BM25 + Dense 各取 top-k | `rag/retrieval/hybrid_retriever.py` |
| 融合 | RRF（k=60） | `rag/retrieval/fusion.py` |
| 重排 | 远程 rerank → 本地 cross-encoder → 原序 | `rag/retrieval/reranker.py` |
| 上下文扩展 | 同章节/相邻块/链接块 | `rag/retrieval/context_builder.py` |
| 查询改写 | 跨语言 query pack + 历史改写 + 术语扩展 | `rag/retrieval/query_rewriter.py` 等 |
| 引用校验 | 检查回答里的 `[Section: X]` 是否在召回集合中 | `rag/answer.py:292-296` |
| 离线评测 | 检索指标 / RAGAS / LLM Judge | `backend/src/ariadne_eval` |

所以问题不是「要不要从 naive 升级」，而是：**这套工程化 RAG 是否覆盖产品所需的问题类型。**

## 1. 按功能判断：哪些够，哪些不够

| 功能 | 需要的能力 | 当前够不够 | 要补什么 |
|---|---|---|---|
| 单篇事实问答 | 混合召回 + 重排 + 上下文扩展 | **够** | 生成侧补历史；引用改到 chunk 级 |
| 5 分钟速读卡 | 整篇结构 + 分层摘要 | **不够** | 用 DocumentIR 大纲做 map-reduce 摘要，不是 top-k 检索 |
| 章节摘要 | 章节定位 + 摘要 | **基本够** | 章节过滤 + 分层摘要；不要用全文 top-k |
| 跨论文问答 | collection 级索引 / 多索引融合 + paper 过滤 | **不够** | 建 collection 快照或 per-paper 索引融合 |
| 多论文对比 | 按论文拆解问题 + 结构化抽取 + 聚合 | **不够** | query decomposition + 统一字段 schema |
| 文献综述矩阵 | 同上 + 导出 | **不够** | 对比表复用，加导出与人工校对 |
| 图表/公式问答 | 结构化块过滤 + 多模态 | **部分** | 先按 `chunk_type` 过滤；图像理解后置 |
| 相关论文/引用网络 | 引用元数据/图 | **不够** | 接 OpenAlex/Semantic Scholar，做元数据图，不是向量 RAG |
| Feed/推荐 | 元数据 + 相关性排序 | **不是 RAG 问题** | 走推荐/规则，不要硬套 RAG |
| 阅读进度/笔记 | 业务数据 | **与 RAG 无关** | 走 M0 的 papers/annotations |

关键判断：

- **单篇阅读（M1）不需要更复杂的 RAG。** 当前 hybrid + rerank 已经超过大多数论文问答产品；真正缺的是摘要编排、历史注入和引用粒度。
- **跨论文综合（M2）需要「模块化 RAG」，不是「更深的向量检索」。** 把问题拆成每篇论文的子问题，分别检索/抽取，再聚合；这比在一个大索引里 top-k 更可靠。
- **全局摘要不是 RAG。** 「这篇论文讲了什么」不应该靠 top-k 片段拼接；应该沿 DocumentIR 的章节树做分层摘要，并缓存。
- **引用关系不是 RAG。** 「谁引用了它 / 它引用了谁」需要元数据图，向量检索帮不上忙。

## 2. 需要补的 7 件事（都不算「复杂 RAG」）

### 2.1 生成侧注入历史（优先级最高）

现状：历史只用于检索改写；生成 prompt 只有片段 + 当前问题。

- `application/chat.py:222-227` 把 `history` 传给 `chat_pipeline.stream_answer`
- `rag/answer.py:181` 的 `stream_answer` 只把 `history` 传给检索
- `adapters/llm/prompt_template.py:7` 的 `build_prompt(chunks, question)` 没有 history 参数

后果：追问「它的参数量是多少」时，检索能命中正确片段，但模型不知道「它」指谁。修复成本很低：在 prompt 中加入最近 2 轮原文 + 更早轮次摘要，按 token 预算截断。

### 2.2 元数据过滤检索

当前检索没有 `paper_id` / `section` / `chunk_type` 过滤；M0 的 `papers` / `chunks.paper_id` 落地后，应该支持：

- 只在当前论文内检索（单篇阅读默认）
- 只在当前章节内检索（章节摘要/解释）
- 只检索表格/公式/图注（结构化问题）
- 只在 collection 内检索（跨论文）

这不是新 RAG 范式，只是给现有 retriever 加过滤条件。

### 2.3 分层摘要（5 分钟速读卡 / 章节摘要）

不要用 top-k 检索做整篇摘要。推荐：

1. 用 `DocumentIR` 的 outline 定位章节；
2. 每节取该节全部 chunk（或按 token 预算分段）；
3. 生成 section summary，强制带 section/page 引用；
4. 汇总成 TL;DR / 贡献 / 方法 / 实验 / 局限；
5. 按论文版本缓存，避免重复烧 token。

这是 map-reduce summarization，不是 RAG 检索。

### 2.4 引用校验从 section 级升到 chunk 级

当前 `rag/answer.py:292-296` 只检查：

~~~python
valid_sections = {chunk.metadata.section for chunk in retrieved_chunks}
cited_sections = set(CITATION_PATTERN.findall(answer))
return bool(cited_sections) and cited_sections.issubset(valid_sections)
~~~

问题：

- 多篇论文都有 `Method` 章节时，无法区分；
- 引用了一个被召回的章节，但具体结论可能来自另一个片段；
- 没有校验「这句话是否真的被该 chunk 支持」。

建议：

- 引用格式改为 `[paper_id:chunk_index]` 或结构化 citation 对象；
- 生成后校验 citation 是否在召回集合；
- 对高风险结论（数字、对比、结论）做 claim-level 支持检查；
- 校验失败时降级为「不确定」或拒答，而不是只给 warning。

### 2.5 查询路由（不是 Agent）

按问题类型走不同管线，而不是所有问题都走同一条 hybrid：

| 问题类型 | 管线 |
|---|---|
| 事实查找 | hybrid + rerank + 上下文扩展 |
| 章节解释 | section filter + 同章节扩展 |
| 整篇摘要 | 分层摘要（map-reduce） |
| 跨论文对比 | 按论文拆子问题 + 结构化抽取 + 聚合 |
| 图表/公式 | chunk_type 过滤 + 结构化提示 |
| 引用关系 | 元数据/图查询 |

一个确定性的分类器 + 少量模板就够了；不需要自主规划循环。

### 2.6 Collection 级检索

M0 的索引仍按 session 构建；M2 需要：

- 方案 A：为每个 collection 建一个快照（简单，但重复存储）；
- 方案 B：每篇论文一个索引，查询时多索引召回 + RRF 融合（更灵活，推荐）；
- 两者都要支持 `paper_id` 过滤与去重。

这属于索引 scope 上移，不是换向量库。

### 2.7 结构化抽取做对比

多论文对比不要直接让 LLM 看 8 个混合片段。推荐：

1. 定义统一 schema：方法 / 数据集 / 指标 / 超参 / 局限；
2. 每篇论文单独检索并抽取成 JSON；
3. 用表格聚合，缺字段明确标「未提及」；
4. 每个字段保留 citation；
5. 导出 Markdown/CSV。

这比「更大的上下文窗口」更可靠，也更便宜。

## 3. 什么时候才需要更复杂的 RAG

### GraphRAG 的触发条件

只有当以下条件同时成立时才考虑：

- 用户大量问「跨论文的多跳关系」（A 的方法是否被 B 改进、C 和 D 的结论是否冲突）；
- 已经有可用的引用图/作者/机构/数据集元数据；
- 评测显示普通 collection RAG 的多跳失败率持续 > 20%；
- 愿意承担实体抽取、图构建与增量更新成本。

现在三条都不成立：没有引用图数据，产品也还没验证多跳是主要问题。

### Agentic RAG 的触发条件

只有当问题需要「多步工具调用」时才考虑：

- 需要边检索边计算（例如统计多篇论文的实验表格）；
- 需要外部搜索/数据库查询；
- 单轮 RAG 的失败主要是「步骤不够」而不是「召回不准」。

当前单篇阅读的失败更可能是历史丢失、摘要编排、引用粒度，而不是需要自主 Agent。先修这些，收益更高。

### 多模态 RAG 的触发条件

- 图表/公式问题占比显著上升；
- MinerU 的结构化表格/公式不够用；
- 愿意承担图像切分、VLM 调用与存储成本。

先做 `chunk_type` 过滤与表格文本检索，成本低得多。

## 4. 推荐路线

| 阶段 | RAG 改动 | 目的 |
|---|---|---|
| M0 | 不改 RAG | 先把 papers/chunks/annotations 数据模型做好 |
| M1 | 历史注入、paper/section 过滤、分层摘要、chunk 级引用 | 单篇读得懂、答得准 |
| M2 | collection 检索、查询路由、结构化对比抽取 | 跨论文综合 |
| M3 | 不做 RAG，做元数据/推荐 | 领域跟进不是 RAG 问题 |
| M4 | 引用图/元数据图（如需要） | 相关论文与引用关系 |

**明确不建议现在做：**

- GraphRAG：没有图数据，也没有证据表明多跳是主要瓶颈。
- 自主 Agent/多轮反思：延迟和成本不可控，评测困难。
- 微调：先修检索、prompt、引用，再谈模型。
- 换向量数据库：FAISS 精确检索在个人文献库规模足够；到 10 万+ chunk 或多用户再评估。
- 多模态 RAG：先用结构化块过滤，图像理解后置。

## 5. 用评测决定是否升级

不要凭感觉增加复杂度。用 `ariadne_eval` 建一个小规模标注集（每类 30–50 题）：

| 指标 | 目标 | 不达标时的动作 |
|---|---|---|
| 单篇 recall@10 | ≥ 0.85 | 调 chunk/retrieval/rerank，不是上 GraphRAG |
| 引用精确率 | ≥ 0.9 | 改引用格式与校验，不是换模型 |
| 忠实度（faithfulness） | ≥ 0.9 | 补 provenance/拒答，不是加 Agent |
| 跨论文对比准确率 | ≥ 0.8 | 加 query decomposition + 结构化抽取 |
| 多跳失败率 | < 20% | 超过再评估 GraphRAG |

## 6. 一句话结论

**M1 不需要更复杂的 RAG，只需要把现有工程化 RAG 的四个缺口补上：历史、过滤、分层摘要、引用粒度。M2 需要模块化 RAG（collection 检索 + 查询路由 + 结构化抽取），但仍不需要 GraphRAG 或 Agent。等评测证明多跳/工具调用是主要瓶颈，再升级。**
