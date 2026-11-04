<script setup lang="ts">
import type { CollectionSummary } from "../../api";

defineProps<{
  collections: CollectionSummary[];
  selectedId: string;
  paperCount: number;
}>();

const emit = defineEmits<{
  select: [collectionId: string];
}>();
</script>

<template>
  <header class="synthesis__bar">
    <div>
      <p class="synthesis__eyebrow">Synthesis · 集合内 {{ paperCount }} 篇</p>
      <h1 class="synthesis__title">跨论文综合</h1>
      <p class="synthesis__subtitle">在同一集合内提问、对比方法与结果。</p>
    </div>
    <label class="synthesis__collection">
      <span>集合</span>
      <select
        :value="selectedId"
        @change="emit('select', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">选择集合</option>
        <option v-for="collection in collections" :key="collection.id" :value="collection.id">
          {{ collection.name }}（{{ collection.paper_count }}）
        </option>
      </select>
    </label>
  </header>
</template>

<style scoped>
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
</style>
