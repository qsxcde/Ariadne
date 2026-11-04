<script setup lang="ts">
import StateBlock from "@/shared/components/StateBlock.vue";
import { MATRIX_FIELDS, useSynthesis } from "@/pages/synthesis/useSynthesis";

const props = defineProps<{
  mode: "compare" | "matrix";
}>();

const emit = defineEmits<{
  open: [paperId: string];
}>();

const {
  papers,
  selectedPaperIds,
  comparison,
  fieldCoverage,
  isComparing,
  togglePaper,
  compare,
} = useSynthesis();

const modeLabel = () => (props.mode === "matrix" ? "综述矩阵" : "对比表");
</script>

<template>
  <aside class="synthesis__selector">
    <header class="synthesis__pane-head">
      <h2>选择论文</h2>
      <span>{{ selectedPaperIds.length }}/5</span>
    </header>
    <StateBlock
      v-if="!papers.length"
      kind="empty"
      compact
      description="这个集合还没有论文。"
    />
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
        <button type="button" class="synthesis__open" @click="emit('open', paper.id)">打开</button>
      </li>
    </ul>
    <button
      type="button"
      class="synthesis__primary synthesis__generate"
      :disabled="isComparing || selectedPaperIds.length < 2"
      @click="compare"
    >
      {{ isComparing ? "生成中…" : `生成${modeLabel()}` }}
    </button>
  </aside>

  <section class="synthesis__result">
    <div v-if="!comparison.length" class="synthesis__empty-wrap">
      <StateBlock
        kind="empty"
        compact
        :title="`还没有生成${modeLabel()}`"
        :description="
          `在左侧选择 2–5 篇论文，再生成${modeLabel()}；结果会按方法、数据集、指标与局限对齐。`
        "
      />
    </div>

    <div v-else class="synthesis__table-wrap">
      <table class="synthesis__table">
        <thead>
          <tr>
            <th class="synthesis__sticky-col">论文</th>
            <th v-for="field in MATRIX_FIELDS" :key="field.key">{{ field.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in comparison" :key="row.paper_id">
            <th class="synthesis__sticky-col">{{ row.title }}</th>
            <td v-for="field in MATRIX_FIELDS" :key="field.key">
              {{ row[field.key] || "未提及" }}
            </td>
          </tr>
          <tr v-if="mode === 'matrix'" class="synthesis__coverage">
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

<style scoped>
.synthesis__selector {
  min-width: 0;
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
  color: var(--color-text-muted);
  font-size: 10px;
  opacity: 0;
}

.synthesis__paper-list li:hover .synthesis__open:hover {
  color: var(--color-text);
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
  color: var(--color-text);
  font-weight: 700;
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
  min-height: 320px;
  border-left: 1px solid var(--color-border);
  padding-left: 28px;
}

.synthesis__empty-wrap {
  display: flex;
  min-height: 300px;
  align-items: center;
  justify-content: center;
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

@media (max-width: 1100px) {
  .synthesis__result {
    border-left: 0;
    padding-left: 0;
  }
}
</style>
