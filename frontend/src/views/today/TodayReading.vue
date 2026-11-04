<script setup lang="ts">
import StateBlock from "../../components/StateBlock.vue";
import { useToday } from "../../composables/useToday";
import type { PaperSummary } from "../../api";

const emit = defineEmits<{
  open: [paperId: string];
  library: [];
}>();

const { reading, readingPreview, progressPercent, authorLine } = useToday();

function openPaper(paper: PaperSummary): void {
  emit("open", paper.id);
}
</script>

<template>
  <section class="today__reading">
    <header class="today__section-head">
      <h2>继续阅读</h2>
      <div class="today__head-actions">
        <span>{{ reading.length }} 篇在读</span>
        <button
          v-if="reading.length"
          type="button"
          class="today__primary today__primary--small"
          @click="openPaper(reading[0])"
        >
          继续上次阅读
        </button>
      </div>
    </header>

    <StateBlock
      v-if="!reading.length"
      kind="empty"
      compact
      title="还没有在读的论文"
      description="去文献库打开一篇，阅读进度会自动记录。"
      action-label="去文献库"
      @action="emit('library')"
    />

    <article
      v-for="(paper, index) in readingPreview"
      :key="paper.id"
      class="reading-item"
      tabindex="0"
      role="button"
      @click="openPaper(paper)"
      @keyup.enter="openPaper(paper)"
    >
      <span class="reading-item__index">{{ String(index + 1).padStart(2, "0") }}</span>
      <div class="reading-item__main">
        <h3 class="reading-item__title">{{ paper.title }}</h3>
        <p class="reading-item__meta">{{ authorLine(paper) }}</p>
        <div class="reading-item__track" aria-hidden="true">
          <span :style="{ width: progressPercent(paper) + '%' }" />
        </div>
      </div>
      <span class="reading-item__pct">{{ progressPercent(paper) }}%</span>
    </article>

    <p v-if="reading.length > 5" class="today__more">
      还有 {{ reading.length - 5 }} 篇在读，去文献库查看全部。
    </p>
  </section>
</template>

<style scoped>
.today__reading {
  min-width: 0;
}

.today__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.today__section-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.today__section-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.today__head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.today__primary {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 8px 16px;
  color: var(--color-white);
  font-size: 12px;
  letter-spacing: 0.03em;
}

.today__primary:hover {
  background: var(--color-accent-strong);
}

.today__primary--small {
  padding: 4px 10px;
  font-size: 11px;
}

.reading-item {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 2px;
  cursor: pointer;
}

.reading-item:last-of-type {
  border-bottom: 0;
}

.reading-item:hover .reading-item__title {
  text-decoration: underline;
  text-decoration-color: var(--color-accent);
  text-underline-offset: 3px;
}

.reading-item__index {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 11px;
}

.reading-item__main {
  min-width: 0;
  flex: 1;
}

.reading-item__title {
  margin: 0 0 5px;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-item__meta {
  margin: 0 0 9px;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-item__track {
  height: 3px;
  overflow: hidden;
  background: var(--color-surface-muted);
}

.reading-item__track span {
  display: block;
  height: 100%;
  background: var(--color-aqua);
}

.reading-item__pct {
  width: 38px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-align: right;
}

.today__more {
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 11px;
}
</style>
