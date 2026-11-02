# 范围偏差与待确认的延期项（2026-11-03）

> 目的：如实记录当前交付与 phase-tasks-2026-11-03.md / test-plan-2026-11-03.md 原始基线的差异。
> 状态：**待用户签收**。在用户明确接受以下延期项之前，不得宣称「所有阶段按原始基线全部完成」。

## 1. 原始基线 vs 实际基线

| 阶段 | 原始计划基线 | 实际交付基线 | 是否等价 |
|---|---|---|---|
| M1 | DeepSeek + 50 题真实论文 QA，citation precision ≥0.9；20 个多轮脚本 ≥90% | 真实 arXiv abstracts 50 题：45/50 正确、47/50 引用；多轮 20/20 | 部分等价：真实摘要语料与多轮门禁通过，provider 不是 DeepSeek |
| M2 | 10 篇真实论文对比，准确率 ≥0.8；30 题跨论文 ≥0.8 | 真实 10 篇摘要对比引用 10/10；跨论文 26/30（86.7%） | 部分等价：跨论文门禁通过，对比准确率未人工标注 |
| M3 | 真实 arXiv 抓取 | 真实 arXiv API 已验证（10 条结果） | 是 |
| M4 | Zotero/Notion OAuth 双向同步、真实 SMTP 邮箱、引用覆盖率 ≥80% | token-based Zotero/Notion 导出；MailHog SMTP 实测；OpenAlex 5 篇抽测 4/5 可解析 | 部分等价：覆盖率恰好 80%，OAuth/真实邮箱未闭环 |
| 部署 | 前后端 Docker 镜像 | docker-compose.app.yml 构建/启动，前端与 /health 验证通过 | 是 |

## 2. 当前明确未完成项

1. **DeepSeek provider 质量评测**
   backend/.env 的 DEEPSEEK_API_KEY 返回 401。未执行 DeepSeek 50 题/10 篇真实评测。

2. **完整 PDF 精读评测**
   真实 arXiv abstracts 50 题达到 45/50 正确（90%）、47/50 引用（94%），10 篇对比引用 10/10。全文 PDF 探索：3 篇真实 PDF 可解析（6/27/30 页）；本地 3B + 4k 上下文下元数据问答 1/9，且标注来自 arXiv 元数据、与 PDF 作者顺序可能不一致，结果不可作为门禁。需要人工标注集 + DeepSeek/大上下文模型才能给出可信的全文精读准确率。

3. **Zotero / Notion OAuth 双向同步**
   已实现 CSL JSON / Markdown 导出与 token-based 官方 API 导出；OAuth 授权、回调、双向同步未实现。

4. **真实外部 SMTP 邮箱**
   MailHog 已验证 SMTP 协议链路；未用真实邮箱服务商账号投递。

5. **后端镜像体积**
   已构建并启动验证，但包含 torch/faiss/mineru，镜像较大；尚未做镜像瘦身/多阶段拆分。

6. **E6 结构收尾**
   `PaperWorkspace.vue` / `PaperReader.vue` 仍超过 300 行，后端仍有模块级 `settings` 引用；属于结构性债务，未在功能阶段内完成。

7. **M3.7 两周转化验证**
   M3 的退出条件要求「连续两周每周至少 1 篇 Feed→阅读」，属于时间型验证，当前只能提供功能与单次转化用例，无法在一天内完成。

## 3. 已完成且可复核的证据

- M0：schema v8、v7/v5 迁移、论文资产/阅读闭环，commit 7626a0a。
- M1/M2：历史注入、scope 检索、chunk 引用、brief/explain、Today、集合问答、对比、周报、导出。
- M3：订阅/Feed、真实 arXiv、Docker mock LLM。
- M4：提醒/Digest、Feed/引用/arXiv 版本检查、OpenAlex 引用（按标题检索 + 相似度校验）、CSL/Markdown/BibTeX、通知 outbox、Webhook + SMTP。
- 测试：
  - 普通 pytest：211 passed, 9 skipped。
  - 前端 vitest：16 passed。
  - 本地真实模型：50 题 QA（45/50）、20 个多轮脚本（20/20）、30 题跨论文（26/30）、10 篇对比引用（10/10）。
  - Docker mock LLM：3 passed。
  - MailHog SMTP：1 passed。
  - 真实 arXiv / OpenAlex：2 passed。
  - 应用 compose：构建/启动/前端/health 通过。

## 4. 需要用户签收的选项

**A. 接受当前范围，延期以下项**
- DeepSeek provider 发布评测；
- 真实论文 corpus 评测；
- Zotero/Notion OAuth 双向同步；
- 真实外部邮箱投递。
接受后，M1/M2 可标记为「本地模型门禁通过、provider 评测延期」，M4 可标记为「导出/通知完成、OAuth 延期」。

**B. 提供凭据，按原始基线补测**
- 有效 DEEPSEEK_API_KEY；
- 真实 Zotero/Notion OAuth 应用凭据；
- 真实 SMTP 账号；
- 真实论文样本与标注集。
提供后继续跑原始发布级评测，不修改门禁定义。

**C. 只接受部分延期**
请明确哪些项接受延期、哪些必须补测。

## 5. 结论

当前工程实现与自动化测试是真实的。真实 arXiv abstracts 50 题/10 篇门禁已通过；仍待闭环的是 **DeepSeek provider 评测、完整 PDF 精读标注集、OAuth 双向同步、真实外部邮箱**。在用户签收 A/B/C 之前，项目状态应标记为「核心功能与真实摘要门禁完成，发布级 provider/集成待确认」。
