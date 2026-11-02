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

- 后端 pytest：156 passed，4 skipped（3 个 Docker mock 用例 + 1 个真实 arXiv 网络用例默认 skip）。
- 前端 Vitest：8 passed；typecheck/lint/build 通过。
- ruff / mypy：通过。
- Docker mock LLM：`./scripts/run_mock_llm_tests.sh` → 3 passed。
- v5 真实开发库副本迁移 v10：user_version 提升、关联回填、FK check 为空。

## 3. 未达成的发布门禁

### 3.1 真实模型评测（阻塞）

- 现象：`backend/.env` 的 `DEEPSEEK_API_KEY` 返回 401 Authentication Fails。
- 影响：M1 的 citation precision、3 篇真实速读卡、多轮评测；M2 的 10 篇课题与对比准确率；M3/M4 的真实摘要/推荐/提醒文案。
- 已做：Docker mock LLM 验证了 OpenAI 兼容 HTTP 链路（completion/embedding/brief/explain/stream）。
- 未做：真实 provider 质量评测；不能用 mock 结果冒充。
- 解除：在 `backend/.env` 填入有效 Key，然后运行真实评测集。

### 3.2 外部数据与集成（未授权/未接入）

- 真实 arXiv 抓取：**已验证**。`ArxivFeedSource` 实际调用 arXiv API，返回 10 条结果，标题/URL/推荐理由正确；可用 `SCIPAL_NETWORK_TESTS=1 pytest tests/test_arxiv_network.py` 复现。
- Zotero / Notion 同步：未接入 OAuth 与 API；当前只有 BibTeX / Markdown / CSV 导出。
- 邮件/推送提醒：Settings 只保存本地偏好，未接投递通道。
- 引用网络：未接 OpenAlex/Semantic Scholar；当前只有站内来源引用。

## 4. 可以立即继续的工作（不依赖 Key）

1. E5：应用本身的 Dockerfile/compose（当前只有测试中间件 compose）。
2. E2：补 Today/Feed/Synthesis 的前端组件测试。
3. E6：拆 PaperReader、settings 注入、status/warning 呈现。
4. M2：术语表、公式/表格解释（可用 mock 测试）。
5. M4：BibTeX 之外 RIS 导出、Digest 页面化。

## 5. 结论

工程代码已覆盖 M0–M4 的核心闭环，Docker 测试中间件与各阶段测试计划已落地；**唯一无法在当前环境闭环的是真实模型质量评测和外部服务授权**。在有效 Key 与网络/授权到位前，不应宣称发布门禁通过。
