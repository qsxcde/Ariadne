<script setup lang="ts">
import { computed } from "vue";
import { Search, Plus } from "@element-plus/icons-vue";

import type { CollectionSummary } from "@/api";

const props = defineProps<{
  filters: { status: string; collectionId: string; tag: string; query: string };
  collections: CollectionSummary[];
}>();

const emit = defineEmits<{
  "update:query": [value: string];
  "update:collectionId": [value: string];
  "update:tag": [value: string];
  changeStatus: [status: string];
  reload: [];
  createCollection: [];
}>();

const query = computed({
  get: () => props.filters.query,
  set: (value: string) => emit("update:query", value),
});

const collectionId = computed({
  get: () => props.filters.collectionId,
  set: (value: string) => emit("update:collectionId", value),
});

const tag = computed({
  get: () => props.filters.tag,
  set: (value: string) => emit("update:tag", value),
});

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "inbox", label: "待读" },
  { value: "queued", label: "队列" },
  { value: "skimming", label: "速读" },
  { value: "reading", label: "在读" },
  { value: "read", label: "已读" },
  { value: "archived", label: "归档" },
];
</script>

<template>
  <div class="paper-library__toolbar">
    <div class="paper-library__statuses" role="group" aria-label="阅读状态">
      <button
        v-for="option in STATUS_OPTIONS"
        :key="option.value"
        type="button"
        class="paper-library__status"
        :class="{ 'is-active': filters.status === option.value }"
        @click="emit('changeStatus', option.value)"
      >
        {{ option.label }}
      </button>
    </div>

    <div class="paper-library__controls">
      <label class="paper-library__search-wrap">
        <Search class="paper-library__search-icon" />
        <input
          v-model="query"
          class="paper-library__search"
          type="search"
          placeholder="搜索标题或作者…"
          @keyup.enter="emit('reload')"
        />
      </label>
      <select v-model="collectionId" class="paper-library__select" @change="emit('reload')">
        <option value="">全部集合</option>
        <option v-for="collection in collections" :key="collection.id" :value="collection.id">
          {{ collection.name }}（{{ collection.paper_count }}）
        </option>
      </select>
      <button type="button" class="paper-library__text-button" @click="emit('createCollection')">
        <Plus class="paper-library__button-icon" /> 新建集合
      </button>
      <input
        v-model="tag"
        class="paper-library__tag-input"
        type="text"
        placeholder="标签"
        @keyup.enter="emit('reload')"
      />
      <button type="button" class="paper-library__text-button" @click="emit('reload')">刷新</button>
      <span class="paper-library__hint">J/K 移动 · Enter 打开 · S 已读</span>
    </div>
  </div>
</template>

<style scoped>
.paper-library__controls,
.paper-library__statuses {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-library__controls {
  flex: 1 1 560px;
  justify-content: flex-end;
}

.paper-library__text-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 11px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.paper-library__button-icon {
  width: 13px;
  height: 13px;
}

.paper-library__text-button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.paper-library__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
}

.paper-library__status {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 5px 2px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-library__status + .paper-library__status {
  margin-left: 10px;
}

.paper-library__status.is-active {
  border-bottom-color: var(--color-text);
  color: var(--color-text);
  font-weight: 600;
}

.paper-library__search-wrap {
  position: relative;
  display: flex;
  min-width: 210px;
  flex: 1 1 240px;
  align-items: center;
}

.paper-library__search-icon {
  position: absolute;
  left: 9px;
  width: 13px;
  color: var(--color-text-muted);
  pointer-events: none;
}

.paper-library__search {
  width: 100%;
  min-width: 0;
  padding-left: 28px;
}

.paper-library__search,
.paper-library__select,
.paper-library__tag-input {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.paper-library__tag-input {
  width: 100px;
}

.paper-library__hint {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}
</style>
