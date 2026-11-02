<script setup lang="ts">
import { computed, onMounted } from "vue";
import { usePapers } from "../composables/usePapers";
import type { PaperSummary } from "../api";

const emit = defineEmits<{
  open: [paperId: string];
  library: [];
  settings: [];
}>();

const { papers, isLoading, errorMessage, loadLibrary } = usePapers();

const reading = computed(() =>
  papers.value
    .filter((paper) => paper.reading_status === "reading")
    .sort((a, b) => (b.last_read_at ?? "").localeCompare(a.last_read_at ?? "")),
);
const queue = computed(() =>
  papers.value
    .filter((paper) => paper.reading_status === "queued" || paper.reading_status === "inbox")
    .slice(0, 8),
);
const readThisWeek = computed(() => {
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  return papers.value.filter((paper) => {
    if (paper.reading_status !== "read" || !paper.last_read_at) return false;
    return new Date(paper.last_read_at).getTime() >= cutoff;
  }).length;
});

function progressPercent(paper: PaperSummary): number {
  return Math.round(Math.max(0, Math.min(1, paper.progress)) * 100);
}

function openPaper(paper: PaperSummary): void {
  emit("open", paper.id);
}

onMounted(() => {
  void loadLibrary();
});
</script>

<template>
  <section class="today" aria-label="Today">
    <header class="today__bar">
      <div>
        <p class="today__eyebrow">Today</p>
        <h1 class="today__title">今天读什么</h1>
        <p class="today__subtitle">继续上次的阅读，或从队列里挑一篇。</p>
      </div>
      <div class="today__actions">
        <button type="button" class="today__button" @click="emit('library')">文献库</button>
        <button type="button" class="today__button" @click="emit('settings')">设置</button>
      </div>
    </header>

    <p v-if="errorMessage" class="today__error">{{ errorMessage }}</p>
    <p v-if="isLoading && !papers.length" class="today__state">正在读取阅读进度…</p>

    <div class="today__grid">
      <section class="today__panel today__panel--wide">
        <header class="today__panel-head">
          <h2>继续阅读</h2>
          <span>{{ reading.length }} 篇在读</span>
        </header>
        <p v-if="!reading.length" class="today__empty">还没有在读的论文。去文献库打开一篇吧。</p>
        <article
          v-for="paper in reading"
          :key="paper.id"
          class="today-paper"
          tabindex="0"
          role="button"
          @click="openPaper(paper)"
          @keyup.enter="openPaper(paper)"
        >
          <div class="today-paper__main">
            <h3>{{ paper.title }}</h3>
            <p>
              <span v-if="(paper.authors ?? []).length">{{ (paper.authors ?? []).slice(0, 2).join("、") }}</span>
              <span v-if="paper.year"> · {{ paper.year }}</span>
            </p>
            <div class="today-paper__track" aria-hidden="true">
              <span :style="{ width: `${progressPercent(paper)}%` }" />
            </div>
          </div>
          <span class="today-paper__progress">{{ progressPercent(paper) }}%</span>
        </article>
      </section>

      <section class="today__panel">
        <header class="today__panel-head">
          <h2>本周</h2>
          <span>目标 3 篇</span>
        </header>
        <p class="today__metric">{{ readThisWeek }}<small> / 3 篇读完</small></p>
        <p class="today__hint">读完的论文会进入文献库「已读」，笔记仍可回看。</p>
      </section>

      <section class="today__panel">
        <header class="today__panel-head">
          <h2>阅读队列</h2>
          <span>{{ queue.length }} 篇</span>
        </header>
        <p v-if="!queue.length" class="today__empty">队列是空的。</p>
        <ul v-else class="today__queue">
          <li v-for="paper in queue" :key="paper.id">
            <button type="button" @click="openPaper(paper)">{{ paper.title }}</button>
            <span>{{ paper.reading_status === "queued" ? "队列中" : "待读" }}</span>
          </li>
        </ul>
      </section>
    </div>
  </section>
</template>

<style scoped>
.today {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  padding: 28px 34px;
  overflow-y: auto;
  background: var(--color-bg);
}

.today__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.today__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.today__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
}

.today__subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.today__actions {
  display: flex;
  gap: 8px;
}

.today__button {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 12px;
  padding: 7px 11px;
}

.today__button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.today__grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr);
  gap: 14px;
}

.today__panel {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-panel);
}

.today__panel--wide {
  grid-row: span 2;
}

.today__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.today__panel-head h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 15px;
}

.today__metric {
  margin: 10px 0 8px;
  color: var(--color-accent);
  font-size: 34px;
  font-weight: 650;
}

.today__metric small {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 400;
}

.today__hint,
.today__empty {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.today__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
}

.today__state {
  color: var(--color-text-muted);
  font-size: 13px;
}

.today-paper {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  cursor: pointer;
}

.today-paper + .today-paper {
  margin-top: 8px;
}

.today-paper:hover {
  border-color: var(--color-accent);
}

.today-paper__main {
  min-width: 0;
  flex: 1;
}

.today-paper__main h3 {
  margin: 0 0 5px;
  overflow: hidden;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today-paper__main p {
  margin: 0 0 8px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.today-paper__track {
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-bg);
}

.today-paper__track span {
  display: block;
  height: 100%;
  background: var(--color-accent);
}

.today-paper__progress {
  color: var(--color-text-muted);
  font-size: 12px;
}

.today__queue {
  margin: 0;
  padding: 0;
  list-style: none;
}

.today__queue li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}

.today__queue li:last-child {
  border-bottom: 0;
}

.today__queue button {
  overflow: hidden;
  border: 0;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  padding: 0;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today__queue span {
  color: var(--color-text-muted);
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .today__grid {
    grid-template-columns: 1fr;
  }

  .today__panel--wide {
    grid-row: auto;
  }
}
</style>
