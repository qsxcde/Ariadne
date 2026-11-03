<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { askCollection, compareCollectionPapers } from "../api/synthesis";
import { listCollections } from "../api/collections";
import { listPapers } from "../api/papers";
import type {
  CollectionAskResult,
  CollectionSummary,
  PaperComparison,
  PaperSummary,
} from "../api";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const collections = ref<CollectionSummary[]>([]);
const selectedCollectionId = ref("");
const papers = ref<PaperSummary[]>([]);
const selectedPaperIds = ref<string[]>([]);
const question = ref("");
const answer = ref<CollectionAskResult | null>(null);
const comparison = ref<PaperComparison[]>([]);
const isLoading = ref(false);
const isAsking = ref(false);
const isComparing = ref(false);
const errorMessage = ref("");
const activeTab = ref<"ask" | "compare" | "matrix">("matrix");

const TABS = [
  { value: "ask", label: "问答" },
  { value: "compare", label: "对比表" },
  { value: "matrix", label: "综述矩阵" },
] as const;

const MATRIX_FIELDS = [
  { key: "method", label: "方法" },
  { key: "datasets", label: "数据集" },
  { key: "metrics", label: "指标" },
  { key: "limitations", label: "局限" },
] as const;

const fieldCoverage = computed(() =>
  MATRIX_FIELDS.map((field) => ({
    ...field,
    covered: comparison.value.filter((row) => {
      const value = (row[field.key] ?? "").trim();
      return value.length > 0 && value !== "未提及";
    }).length,
  })),
);

const selectedCollection = computed(
  () => collections.value.find((item) => item.id === selectedCollectionId.value) ?? null,
);

async function loadCollections(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    collections.value = await listCollections();
    if (!selectedCollectionId.value && collections.value.length) {
      selectedCollectionId.value = collections.value[0].id;
      await loadPapers();
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取集合失败";
  } finally {
    isLoading.value = false;
  }
}

async function loadPapers(): Promise<void> {
  if (!selectedCollectionId.value) {
    papers.value = [];
    return;
  }
  try {
    papers.value = await listPapers({ collectionId: selectedCollectionId.value });
    selectedPaperIds.value = [];
    answer.value = null;
    comparison.value = [];
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取集合论文失败";
  }
}

function togglePaper(paperId: string): void {
  if (selectedPaperIds.value.includes(paperId)) {
    selectedPaperIds.value = selectedPaperIds.value.filter((id) => id !== paperId);
  } else if (selectedPaperIds.value.length < 5) {
    selectedPaperIds.value = [...selectedPaperIds.value, paperId];
  }
}

async function ask(): Promise<void> {
  if (!selectedCollectionId.value || !question.value.trim()) {
    return;
  }
  isAsking.value = true;
  errorMessage.value = "";
  try {
    answer.value = await askCollection(selectedCollectionId.value, question.value.trim());
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "集合问答失败";
  } finally {
    isAsking.value = false;
  }
}

function exportComparison(): void {
  if (!comparison.value.length) return;
  const header = ["论文", "方法", "数据集", "指标", "局限"];
  const rows = comparison.value.map((row) => [
    row.title,
    row.method,
    row.datasets,
    row.metrics,
    row.limitations,
  ]);
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = "paper-comparison.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function escapeMarkdownCell(value: string): string {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replaceAll("\n", " ")
    .trim();
}

function exportMatrixMarkdown(): void {
  if (!comparison.value.length) {
    return;
  }
  const header = `| 论文 | ${MATRIX_FIELDS.map((field) => field.label).join(" | ")} |`;
  const separator = `| --- | ${MATRIX_FIELDS.map(() => "---").join(" | ")} |`;
  const rows = comparison.value.map(
    (row) =>
      `| ${[row.title, ...MATRIX_FIELDS.map((field) => row[field.key])]
        .map(escapeMarkdownCell)
        .join(" | ")} |`,
  );
  const coverage = `\n覆盖：${fieldCoverage.value
    .map((field) => `${field.label} ${field.covered}/${comparison.value.length}`)
    .join(" · ")}`;
  const markdown = [header, separator, ...rows, coverage].join("\n");
  const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = "survey-matrix.md";
  link.click();
  URL.revokeObjectURL(url);
}

async function compare(): Promise<void> {
  if (selectedPaperIds.value.length < 2) {
    ElMessage.warning("至少选择 2 篇论文");
    return;
  }
  isComparing.value = true;
  errorMessage.value = "";
  try {
    comparison.value = await compareCollectionPapers(
      selectedCollectionId.value,
      selectedPaperIds.value,
    );
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "论文对比失败";
  } finally {
    isComparing.value = false;
  }
}

onMounted(() => {
  void loadCollections();
});
</script>

<template>
  <section class="synthesis" aria-label="跨论文综合">
    <header class="synthesis__bar">
      <div>
        <p class="synthesis__eyebrow">Synthesis · 集合内 {{ papers.length }} 篇</p>
        <h1 class="synthesis__title">跨论文综合</h1>
        <p class="synthesis__subtitle">在同一集合内提问、对比方法与结果。</p>
      </div>
      <label class="synthesis__collection">
        <span>集合</span>
        <select v-model="selectedCollectionId" @change="loadPapers">
          <option value="">选择集合</option>
          <option v-for="collection in collections" :key="collection.id" :value="collection.id">
            {{ collection.name }}（{{ collection.paper_count }}）
          </option>
        </select>
      </label>
    </header>

    <div v-if="selectedCollection" class="synthesis__meta">
      <span>{{ selectedCollection.description || "按论文片段回答，引用保留 section 与 chunk。" }}</span>
      <span class="synthesis__counts">
        已读 {{ selectedCollection.by_status?.read ?? 0 }} · 在读
        {{ selectedCollection.by_status?.reading ?? 0 }} · 待读
        {{
          (selectedCollection.by_status?.inbox ?? 0) +
          (selectedCollection.by_status?.queued ?? 0)
        }}
      </span>
    </div>

    <div class="synthesis__tabs-row">
      <div class="synthesis__tabs" role="tablist" aria-label="综合作业">
        <button
          v-for="tab in TABS"
          :key="tab.value"
          type="button"
          role="tab"
          class="synthesis__tab"
          :class="{ 'is-active': activeTab === tab.value }"
          :aria-selected="activeTab === tab.value"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>
      <div v-if="comparison.length" class="synthesis__exports">
        <button
          v-if="activeTab === 'compare'"
          type="button"
          @click="exportComparison"
        >
          导出 CSV
        </button>
        <button
          v-if="activeTab === 'matrix'"
          type="button"
          @click="exportMatrixMarkdown"
        >
          导出 Markdown
        </button>
      </div>
    </div>

    <p v-if="errorMessage" class="synthesis__error">{{ errorMessage }}</p>
    <p v-if="isLoading" class="synthesis__state">正在读取集合…</p>
    <p v-else-if="!collections.length" class="synthesis__state">
      还没有集合。先在文献库里创建集合并加入论文。
    </p>

    <div v-else class="synthesis__body" :class="{ 'synthesis__body--single': activeTab === 'ask' }">
      <section v-if="activeTab === 'ask'" class="synthesis__ask-pane">
        <header class="synthesis__pane-head">
          <h2>集合问答</h2>
          <span>{{ papers.length }} 篇论文</span>
        </header>
        <textarea
          v-model="question"
          class="synthesis__textarea"
          rows="3"
          placeholder="问一个跨论文的问题，例如：这几篇的方法差异是什么？"
        />
        <div class="synthesis__ask-actions">
          <span>回答保留 [Section | Chunk] 引用</span>
          <button
            type="button"
            class="synthesis__primary"
            :disabled="isAsking || !selectedCollectionId || !question.trim()"
            @click="ask"
          >
            {{ isAsking ? "回答中…" : "提问" }}
          </button>
        </div>
        <article v-if="answer" class="synthesis__answer">
          <p>{{ answer.answer }}</p>
          <p class="synthesis__answer-meta">
            引用 {{ answer.sources?.length ?? 0 }} 段 · 覆盖 {{ answer.paper_ids?.length ?? 0 }} 篇论文
          </p>
        </article>
      </section>

      <template v-else>
        <aside class="synthesis__selector">
          <header class="synthesis__pane-head">
            <h2>选择论文</h2>
            <span>{{ selectedPaperIds.length }}/5</span>
          </header>
          <p v-if="!papers.length" class="synthesis__state">这个集合还没有论文。</p>
          <ul v-else class="synthesis__paper-list">
            <li v-for="paper in papers" :key="paper.id">
              <label
                class="synthesis__paper"
                :class="{ 'is-selected': selectedPaperIds.includes(paper.id) }"
              >
                <input
                  type="checkbox"
                  :checked="selectedPaperIds.includes(paper.id)"
                  @change="togglePaper(paper.id)"
                />
                <span class="synthesis__paper-main">
                  <span class="synthesis__paper-title">{{ paper.title }}</span>
                  <span class="synthesis__paper-meta">
                    {{ (paper.authors ?? [])[0] || "未知作者" }}
                    <template v-if="paper.year"> · {{ paper.year }}</template>
                  </span>
                </span>
              </label>
              <button
                type="button"
                class="synthesis__open"
                @click="emit('open', paper.id)"
              >
                打开
              </button>
            </li>
          </ul>
          <button
            type="button"
            class="synthesis__primary synthesis__generate"
            :disabled="isComparing || selectedPaperIds.length < 2"
            @click="compare"
          >
            {{
              isComparing
                ? "生成中…"
                : activeTab === "matrix"
                  ? "生成综述矩阵"
                  : "生成对比表"
            }}
          </button>
        </aside>

        <section class="synthesis__result">
          <p v-if="!comparison.length" class="synthesis__empty">
            选择 2–5 篇论文并生成{{ activeTab === "matrix" ? "综述矩阵" : "对比表" }}。
          </p>

          <div v-else class="synthesis__table-wrap">
            <table class="synthesis__table">
              <thead>
                <tr>
                  <th class="synthesis__sticky-col">论文</th>
                  <th v-for="field in MATRIX_FIELDS" :key="field.key">
                    {{ field.label }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in comparison" :key="row.paper_id">
                  <th class="synthesis__sticky-col">{{ row.title }}</th>
                  <td v-for="field in MATRIX_FIELDS" :key="field.key">
                    {{ row[field.key] || "未提及" }}
                  </td>
                </tr>
                <tr v-if="activeTab === 'matrix'" class="synthesis__coverage">
                  <th class="synthesis__sticky-col">覆盖</th>
                  <td v-for="field in fieldCoverage" :key="field.key">
                    {{ field.covered }}/{{ comparison.length }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </section>
</template>

<style scoped>
.synthesis {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 26px 30px 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.synthesis__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.synthesis__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.synthesis__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
}

.synthesis__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.synthesis__collection {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.synthesis__collection select {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 10px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.synthesis__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__counts {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  white-space: nowrap;
}

.synthesis__tabs-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
}

.synthesis__tabs {
  display: flex;
  gap: 18px;
}

.synthesis__tab {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 8px 2px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.synthesis__tab.is-active {
  border-bottom-color: var(--color-accent);
  color: var(--color-text);
  font-weight: 600;
}

.synthesis__exports {
  display: flex;
  gap: 10px;
}

.synthesis__exports button {
  border: 0;
  background: transparent;
  color: var(--color-accent);
  font-size: 11px;
}

.synthesis__body {
  display: grid;
  min-height: 0;
  grid-template-columns: minmax(240px, 280px) minmax(0, 1fr);
  gap: 28px;
}

.synthesis__body--single {
  grid-template-columns: minmax(0, 1fr);
}

.synthesis__pane-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 10px;
}

.synthesis__pane-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.synthesis__pane-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.synthesis__selector {
  min-width: 0;
}

.synthesis__paper-list {
  margin: 0 0 14px;
  padding: 0;
  list-style: none;
}

.synthesis__paper-list li {
  position: relative;
}

.synthesis__open {
  position: absolute;
  top: 8px;
  right: 2px;
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-accent);
  font-size: 10px;
  opacity: 0;
}

.synthesis__paper-list li:hover .synthesis__open {
  opacity: 1;
}

.synthesis__paper {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  border-bottom: 1px solid var(--color-border);
  padding: 9px 2px;
  cursor: pointer;
}

.synthesis__paper input {
  margin-top: 3px;
  accent-color: var(--color-accent);
}

.synthesis__paper-main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.synthesis__paper-title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.synthesis__paper-meta {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.synthesis__paper.is-selected .synthesis__paper-title {
  color: var(--color-accent-strong);
}

.synthesis__primary {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 7px 14px;
  color: var(--color-white);
  font-size: 12px;
}

.synthesis__primary:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.synthesis__generate {
  width: 100%;
}

.synthesis__result {
  min-width: 0;
}

.synthesis__empty {
  padding: 60px 20px;
  color: var(--color-text-muted);
  font-size: 12px;
  text-align: center;
}

.synthesis__table-wrap {
  max-height: 520px;
  overflow: auto;
  border-top: 1px solid var(--color-border);
}

.synthesis__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.synthesis__table th,
.synthesis__table td {
  border-bottom: 1px solid var(--color-border);
  padding: 9px 10px;
  text-align: left;
  vertical-align: top;
}

.synthesis__table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--color-page);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.synthesis__sticky-col {
  position: sticky;
  left: 0;
  z-index: 2;
  width: 22%;
  background: var(--color-surface);
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 12px;
  font-weight: 600;
}

.synthesis__table thead .synthesis__sticky-col {
  z-index: 3;
  background: var(--color-page);
}

.synthesis__coverage th,
.synthesis__coverage td {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.synthesis__ask-pane {
  max-width: 900px;
}

.synthesis__textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 9px 10px;
  color: var(--color-text);
  font: inherit;
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
}

.synthesis__ask-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__answer {
  margin-top: 18px;
  border-left: 2px solid var(--color-accent);
  padding: 2px 0 2px 14px;
}

.synthesis__answer p {
  margin: 0;
  color: var(--color-text-body);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.synthesis__answer-meta {
  margin-top: 8px !important;
  color: var(--color-text-muted) !important;
  font-family: var(--font-mono);
  font-size: 10px !important;
}

.synthesis__state,
.synthesis__error {
  color: var(--color-text-muted);
  font-size: 12px;
}

.synthesis__error {
  color: var(--color-danger);
}

@media (max-width: 1100px) {
  .synthesis__body {
    grid-template-columns: 1fr;
  }
}
</style>
