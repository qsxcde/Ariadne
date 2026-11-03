<script setup lang="ts">
import { Search } from "@element-plus/icons-vue";

defineProps<{
  section: string;
}>();

const emit = defineEmits<{
  command: [];
  import: [];
}>();
</script>

<template>
  <header class="topbar">
    <div class="topbar__identity">
      <span class="topbar__mark">SciPal</span>
      <span class="topbar__slash" aria-hidden="true">/</span>
      <span class="topbar__section">{{ section }}</span>
    </div>

    <div class="topbar__actions">
      <button type="button" class="topbar__search" @click="emit('command')">
        <Search class="topbar__search-icon" />
        <span class="topbar__placeholder">搜索论文、集合或命令</span>
        <kbd class="topbar__kbd">⌘K</kbd>
      </button>
      <button type="button" class="topbar__action" @click="emit('import')">
        导入
      </button>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  height: 56px;
  flex: 0 0 56px;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
  padding: 0 24px;
}

.topbar__identity {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 10px;
}

.topbar__mark {
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.topbar__slash {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 12px;
}

.topbar__section {
  overflow: hidden;
  color: var(--color-text-muted);
  font-family: var(--font-serif);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar__search {
  display: flex;
  width: min(360px, 32vw);
  align-items: center;
  gap: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 9px;
  color: var(--color-text-muted);
  text-align: left;
}

.topbar__search:hover {
  border-color: var(--color-accent);
}

.topbar__search-icon {
  width: 14px;
}

.topbar__placeholder {
  flex: 1;
  font-size: 12px;
}

.topbar__kbd {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  padding: 0 4px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.topbar__action {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 7px 14px;
  color: var(--color-white);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.topbar__action:hover {
  background: var(--color-accent-strong);
}
</style>
