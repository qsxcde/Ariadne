<script setup lang="ts">
import StateBlock from "@/shared/components/StateBlock.vue";
import { useToday } from "@/pages/today/useToday";
import type { PaperSummary } from "@/api";
import { paperStatusLabel } from "@/shared/constants/paper";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const { queue, authorLine } = useToday();

function openPaper(paper: PaperSummary): void {
  emit("open", paper.id);
}
</script>

<template>
  <section class="today__queue">
    <header class="today__section-head">
      <h2>阅读队列</h2>
      <span>{{ queue.length }} 篇</span>
    </header>
    <StateBlock
      v-if="!queue.length"
      kind="empty"
      compact
      description="队列是空的。把想读的论文标记为「队列中」即可出现在这里。"
    />
    <div v-else class="today__queue-track">
      <button
        v-for="paper in queue"
        :key="paper.id"
        type="button"
        class="queue-item"
        @click="openPaper(paper)"
      >
        <span class="queue-item__status">
          {{ paperStatusLabel(paper.reading_status) }}
        </span>
        <span class="queue-item__title">{{ paper.title }}</span>
        <span class="queue-item__meta">{{ authorLine(paper) }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.today__queue {
  min-width: 0;
}

.today__queue-track {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  border-top: 1px solid var(--color-border);
}

.queue-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  border: 0;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  padding: 12px 16px;
  text-align: left;
}

.queue-item:hover {
  background: var(--color-surface);
}

.queue-item__status {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.queue-item__title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.queue-item__meta {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
