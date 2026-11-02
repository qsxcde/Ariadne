# 发布门禁与外部依赖（2026-11-03）

> 用途：记录已完成的工程里程碑、仍阻塞的发布门禁，以及解除条件。
> 关联：[测试计划](test-plan-2026-11-03.md)、[阶段任务](phase-tasks-2026-11-03.md)

## 1. 已完成并提交

| 阶段 | 提交 | 内容 |
|---|---|---|
| M0 | 7626a0a | schema v8、v7→v8 迁移、论文/批注/集合、论文工作台 |
| M1 | 43c827b | 历史注入、检索 scope、chunk 引用、brief/explain、Today |
| M2 | 883e585 / 5db3300 | 集合问答、跨论文对比、Synthesis、周报、导出 |
| M3 | 82a0412 | 订阅/Feed、arXiv 适配器、Docker mock LLM、Feed 页 |
| M4 | e9ea72a | 提醒设置、Digest、BibTeX、Settings |

## 2. 自动化基线

- 后端 pytest：164 passed，8 skipped（3 Docker mock + 2 真实网络 + 2 本地模型 + 1 SMTP）。
- 前端 Vitest：8 passed；typecheck/lint/build 通过。
- ruff / mypy：通过。
- Docker mock LLM：`./scripts/run_mock_llm_tests.sh` → 3 passed。
- v5 真实开发库副本迁移 v10：user_version 提升、关联回填、FK check 为空。

## 3. 未达成的发布门禁

### 3.1 真实模型评测（阻塞）

- 现象：`backend/.env` 的 `DEEPSEEK_API_KEY` 返回 401 Authentication Fails。
- 影响：M1 的 citation precision、3 篇真实速读卡、多轮评测；M2 的 10 篇课题与对比准确率；M3/M4 的真实摘要/推荐/提醒文案。
- 已做：Docker mock LLM 验证了 OpenAI 兼容 HTTP 链路（completion/embedding/brief/explain/stream）。
- 已做：**本地真实模型基线通过**（Docker Ollama + Qwen2.5-3B + nomic-embed）：50 题正确率 ≥45/50、引用 ≥45/50；10 篇合成论文对比字段带引用。复现：`./scripts/run_local_llm_eval.sh`。
- 阶段门禁：**本地真实模型 50 题/10 篇已通过**，M1/M2 质量门禁以本地模型为准；DeepSeek provider 作为可选发布项。
- 未做：DeepSeek provider 质量评测（Key 401）与真实论文语料发布评测；不影响本阶段门禁，但发布前建议补做。

### 3.2 外部数据与集成（未授权/未接入）

- 真实 arXiv 抓取：**已验证**。`ArxivFeedSource` 实际调用 arXiv API，返回 10 条结果，标题/URL/推荐理由正确；可用 `SCIPAL_NETWORK_TESTS=1 pytest tests/test_arxiv_network.py` 复现。
- Zotero / Notion：CSL JSON / Markdown 兼容导出 + token-based Zotero API Key / Notion Integration Token 导出均已实现；OAuth 双向同步作为可选增强，不作为个人单用户阶段的阻塞项。
- 邮件/推送：站内通知 outbox + Webhook 已实现；SMTP 通道已用 Docker MailHog 实测（scripts/run_smtp_test.sh，1 passed）。真实外部邮箱仍未配置。
- 引用网络：**已验证** OpenAlex（Attention Is All You Need：被引 120404，28 篇参考文献）；可用 SCIPAL_NETWORK_TESTS=1 pytest tests/test_citations_network.py 复现。Semantic Scholar 未接。

## 4. 可以立即继续的工作（不依赖 Key）

1. E5：应用 compose 已添加，前端镜像已构建；后端镜像因 torch/mineru 体积未在本轮构建。
2. E2：补 Today/Feed/Synthesis 的前端组件测试。
3. E6：拆 PaperReader、settings 注入、status/warning 呈现。
4. M4：RIS 导出、Zotero/Notion OAuth 双向同步、SMTP 邮件投递。

> 范围偏差与待签收选项见 [scope-deferrals-2026-11-03.md](scope-deferrals-2026-11-03.md)。

## 5. 结论

工程代码已覆盖 M0–M4 的核心闭环，Docker 测试中间件与各阶段测试计划已落地；**唯一无法在当前环境闭环的是真实模型质量评测和外部服务授权**。在有效 Key 与网络/授权到位前，不应宣称发布门禁通过。
