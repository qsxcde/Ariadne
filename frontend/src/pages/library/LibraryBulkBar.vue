<script setup lang="ts">
import type { CollectionSummary } from "@/api";

defineProps<{
  count: number;
  collections: CollectionSummary[];
  busy: boolean;
  collectionId: string;
}>();

const emit = defineEmits<{
  "update:collectionId": [value: string];
  markRead: [];
  remove: [];
  addToCollection: [];
  clear: [];
}>();
</script>

<template>
  <div class="paper-library__bulk">
    <span class="paper-library__bulk-count">已选 {{ count }} 篇</span>
    <div class="paper-library__bulk-actions">
      <button type="button" :disabled="busy" @click="emit('markRead')">标记已读</button>
      <button
        type="button"
        :disabled="busy"
        class="paper-library__bulk-danger"
        @click="emit('remove')"
      >
        删除
      </button>
      <select
        class="paper-library__select"
        :value="collectionId"
        @change="emit('update:collectionId', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">加入集合…</option>
        <option v-for="collection in collections" :key="collection.id" :value="collection.id">
          {{ collection.name }}
        </option>
      </select>
      <button type="button" :disabled="!collectionId || busy" @click="emit('addToCollection')">
        加入
      </button>
      <button type="button" class="paper-library__bulk-clear" @click="emit('clear')">
        清除选择
      </button>
    </div>
  </div>
</template>

<style scoped>
.paper-library__bulk {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  border: 1px solid var(--color-border);
  border-left: 2px solid var(--color-accent);
  background: var(--color-surface-alt);
  padding: 7px 10px;
}

.paper-library__bulk-count {
  color: var(--color-text);
  font-size: 11px;
  font-weight: 600;
}

.paper-library__bulk-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-library__bulk-actions button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 4px 9px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.paper-library__bulk-actions button:hover:not(:disabled) {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.paper-library__bulk-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.paper-library__bulk-actions .paper-library__bulk-danger {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.paper-library__select {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 4px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 11px;
}

.paper-library__bulk-clear {
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 11px;
  padding: 4px 2px;
}
</style>
