<script setup lang="ts">
import { computed } from "vue";
import { Search } from "@element-plus/icons-vue";
import { shortcutLabel } from "@/shared/utils/platform";

withDefaults(
  defineProps<{
    section: string;
    showSearch?: boolean;
    showImport?: boolean;
  }>(),
  {
    showSearch: true,
    showImport: true,
  },
);

const emit = defineEmits<{
  command: [];
  import: [];
}>();

const searchShortcut = computed(() => shortcutLabel("K"));
</script>

<template>
  <header class="topbar">
    <div class="topbar__identity">
      <span class="topbar__context">工作台</span>
      <span class="topbar__slash" aria-hidden="true">/</span>
      <span class="topbar__section">{{ section }}</span>
    </div>

    <div class="topbar__actions">
      <button
        v-if="showSearch"
        type="button"
        class="topbar__search"
        @click="emit('command')"
      >
        <Search class="topbar__search-icon" />
        <span class="topbar__placeholder">搜索论文、集合或命令</span>
        <kbd class="topbar__kbd">{{ searchShortcut }}</kbd>
      </button>
      <button
        v-if="showImport"
        type="button"
        class="topbar__action"
        @click="emit('import')"
      >
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

.topbar__context {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.topbar__slash {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 11px;
}

.topbar__section {
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 600;
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
  border-color: var(--color-border-strong);
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
  font-size: 9px;
  white-space: nowrap;
}

.topbar__action {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: transparent;
  padding: 6px 13px;
  color: var(--color-accent);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.topbar__action:hover {
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
}
</style>
