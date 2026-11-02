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
  library: [];
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
const activeTab = ref<"ask" | "compare" | "matrix">("ask");

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
        <p class="synthesis__eyebrow">Synthesis</p>
        <h1 class="synthesis__title">跨论文综合</h1>
        <p class="synthesis__subtitle">在一个集合内问答、对比方法与结果。</p>
      </div>
      <div class="synthesis__actions">
        <button type="button" class="synthesis__button" @click="emit('library')">文献库</button>
      </div>
    </header>

    <div class="synthesis__toolbar">
      <label>
        集合
        <select
          v-model="selectedCollectionId"
          class="synthesis__select"
          @change="loadPapers"
        >
          <option value="">选择集合</option>
          <option v-for="collection in collections" :key="collection.id" :value="collection.id">
            {{ collection.name }}（{{ collection.paper_count }}）
          </option>
        </select>
      </label>
      <span v-if="selectedCollection" class="synthesis__hint">
        {{ selectedCollection.description || "按论文片段回答，引用保留 section 与 chunk。" }} ·
        已读 {{ selectedCollection.by_status?.read ?? 0 }} · 在读
        {{ selectedCollection.by_status?.reading ?? 0 }} · 待读
        {{
          (selectedCollection.by_status?.inbox ?? 0) +
          (selectedCollection.by_status?.queued ?? 0)
        }}
      </span>
    </div>

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

    <p v-if="errorMessage" class="synthesis__error">{{ errorMessage }}</p>
    <p v-if="isLoading" class="synthesis__state">正在读取集合…</p>
    <p v-else-if="!collections.length" class="synthesis__state">
      还没有集合。先在文献库里创建集合并加入论文。
    </p>

    <div v-else class="synthesis__grid">
      <section
        v-if="activeTab === 'ask'"
        class="synthesis__panel"
        :class="{ 'synthesis__panel--full': activeTab === 'ask' }"
      >
        <header class="synthesis__panel-head">
          <h2>集合问答</h2>
          <span>{{ papers.length }} 篇论文</span>
        </header>
        <div class="synthesis__ask">
          <textarea
            v-model="question"
            class="synthesis__textarea"
            rows="3"
            placeholder="问一个跨论文的问题，例如：这几篇的方法差异是什么？"
          />
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
          <p class="synthesis__meta">
            引用 {{ answer.sources?.length ?? 0 }} 段 · 覆盖 {{ answer.paper_ids?.length ?? 0 }} 篇论文
          </p>
        </article>
      </section>

      <section v-if="activeTab !== 'ask'" class="synthesis__panel">
        <header class="synthesis__panel-head">
          <h2>{{ activeTab === "matrix" ? "选择综述矩阵论文" : "选择论文对比" }}</h2>
          <span>{{ selectedPaperIds.length }}/5</span>
        </header>
        <p v-if="!papers.length" class="synthesis__state">这个集合还没有论文。</p>
        <ul v-else class="synthesis__paper-list">
          <li v-for="paper in papers" :key="paper.id">
            <label>
              <input
                type="checkbox"
                :checked="selectedPaperIds.includes(paper.id)"
                @change="togglePaper(paper.id)"
              />
              <span>{{ paper.title }}</span>
            </label>
            <button type="button" class="synthesis__link" @click="emit('open', paper.id)">
              打开
            </button>
          </li>
        </ul>
        <button
          type="button"
          class="synthesis__primary synthesis__compare"
          :disabled="isComparing || selectedPaperIds.length < 2"
          @click="compare"
        >
          {{ isComparing ? "对比中…" : "生成对比表" }}
        </button>
      </section>

      <section
        v-if="activeTab === 'compare' && comparison.length"
        class="synthesis__panel synthesis__panel--full"
      >
        <header class="synthesis__panel-head">
          <h2>对比表</h2>
          <button type="button" class="synthesis__link" @click="exportComparison">
            导出 CSV
          </button>
        </header>
        <div class="synthesis__table-wrap">
          <table class="synthesis__table">
            <thead>
              <tr>
                <th>论文</th>
                <th>方法</th>
                <th>数据集</th>
                <th>指标</th>
                <th>局限</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in comparison" :key="row.paper_id">
                <td>{{ row.title }}</td>
                <td>{{ row.method }}</td>
                <td>{{ row.datasets }}</td>
                <td>{{ row.metrics }}</td>
                <td>{{ row.limitations }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 'matrix'" class="synthesis__panel synthesis__panel--full">
        <header class="synthesis__panel-head">
          <h2>综述矩阵</h2>
          <button
            v-if="comparison.length"
            type="button"
            class="synthesis__link"
            @click="exportMatrixMarkdown"
          >
            导出 Markdown
          </button>
        </header>
        <p v-if="!comparison.length" class="synthesis__state">
          选择 2–5 篇论文并生成对比后，这里会按「方法 / 数据集 / 指标 / 局限」排成矩阵。
        </p>
        <template v-else>
          <div class="synthesis__table-wrap">
            <table class="synthesis__table">
              <thead>
                <tr>
                  <th>论文</th>
                  <th v-for="field in MATRIX_FIELDS" :key="field.key">{{ field.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in comparison" :key="row.paper_id">
                  <td>{{ row.title }}</td>
                  <td v-for="field in MATRIX_FIELDS" :key="field.key">
                    {{ row[field.key] || "未提及" }}
                  </td>
                </tr>
                <tr class="synthesis__coverage">
                  <td>覆盖</td>
                  <td v-for="field in fieldCoverage" :key="field.key">
                    {{ field.covered }}/{{ comparison.length }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </section>
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
  padding: 28px 34px;
  overflow-y: auto;
  background: var(--color-bg);
}

.synthesis__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.synthesis__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.synthesis__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
}

.synthesis__subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.synthesis__button,
.synthesis__primary {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 12px;
  padding: 7px 11px;
}

.synthesis__primary {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: #fff;
}

.synthesis__primary:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.synthesis__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-panel);
  color: var(--color-text-muted);
  font-size: 12px;
}

.synthesis__select,
.synthesis__textarea {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  padding: 7px 9px;
}

.synthesis__hint {
  color: var(--color-text-muted);
}

.synthesis__tabs {
  display: flex;
  gap: 6px;
}

.synthesis__tab {
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-panel);
  padding: 6px 12px;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 12px;
}

.synthesis__tab.is-active {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.synthesis__coverage td {
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
}

.synthesis__state {
  color: var(--color-text-muted);
  font-size: 13px;
}

.synthesis__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(260px, 1fr);
  gap: 14px;
}

.synthesis__panel {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-panel);
}

.synthesis__panel--full {
  grid-column: 1 / -1;
}

.synthesis__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.synthesis__panel-head h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 15px;
}

.synthesis__ask {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.synthesis__textarea {
  resize: vertical;
}

.synthesis__answer {
  margin-top: 12px;
  padding: 12px;
  border-left: 3px solid var(--color-accent);
  background: var(--color-bg);
  font-size: 13px;
  line-height: 1.6;
}

.synthesis__answer p {
  margin: 0;
  white-space: pre-wrap;
}

.synthesis__meta {
  margin-top: 8px !important;
  color: var(--color-text-muted);
  font-size: 11px;
}

.synthesis__paper-list {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
}

.synthesis__paper-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}

.synthesis__paper-list label {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 7px;
}

.synthesis__paper-list span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.synthesis__link {
  border: 0;
  background: transparent;
  color: var(--color-accent);
  cursor: pointer;
  font-size: 11px;
}

.synthesis__compare {
  width: 100%;
}

.synthesis__table-wrap {
  overflow-x: auto;
}

.synthesis__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.synthesis__table th,
.synthesis__table td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  vertical-align: top;
}

.synthesis__table th {
  color: var(--color-text-muted);
  font-weight: 600;
}

@media (max-width: 900px) {
  .synthesis__grid {
    grid-template-columns: 1fr;
  }
}
</style>
