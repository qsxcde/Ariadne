<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { Search } from "@element-plus/icons-vue";
import RunStatusBadge from "@/features/agent/components/RunStatusBadge.vue";
import { useAgentRuns } from "@/features/agent/composables/useAgentRuns";
import { shortcutLabel } from "@/shared/utils/platform";

withDefaults(
  defineProps<{
    section: string;
    context?: string;
    showSearch?: boolean;
    showImport?: boolean;
  }>(),
  {
    context: "",
    showSearch: true,
    showImport: true,
  },
);

const emit = defineEmits<{
  command: [];
  import: [];
}>();

const { runningRun, stopRun } = useAgentRuns();
const now = ref(Date.now());
let ticker: number | null = null;

onMounted(() => {
  ticker = window.setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onBeforeUnmount(() => {
  if (ticker !== null) {
    window.clearInterval(ticker);
  }
});

const searchShortcut = computed(() => shortcutLabel("K"));

const runElapsed = computed(() => {
  const run = runningRun.value;
  if (!run) {
    return "";
  }
  const seconds = Math.max(0, Math.round((now.value - run.createdAt) / 1000));
  if (seconds < 60) {
    return `${seconds}s`;
  }
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
});

function stopActiveRun(): void {
  if (runningRun.value) {
    stopRun(runningRun.value.localId);
  }
}
</script>

<template>
  <header class="topbar">
    <div class="topbar__identity">
      <span class="topbar__context">工作台</span>
      <span class="topbar__slash" aria-hidden="true">/</span>
      <span class="topbar__section">{{ section }}</span>
      <template v-if="context">
        <span class="topbar__slash" aria-hidden="true">/</span>
        <span class="topbar__context-title" :title="context">{{ context }}</span>
      </template>
    </div>

    <div class="topbar__actions">
      <div v-if="runningRun" class="topbar__run">
        <RunStatusBadge :status="runningRun.status" compact />
        <span class="topbar__run-goal" :title="runningRun.goal">{{ runningRun.goal }}</span>
        <span class="topbar__run-meta">
          <template v-if="runningRun.steps.length">{{ runningRun.steps.length }} 步 · </template>
          {{ runElapsed }}
        </span>
        <button type="button" class="topbar__run-stop" @click="stopActiveRun">停止</button>
      </div>
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

.topbar__context-title {
  overflow: hidden;
  max-width: 280px;
  color: var(--color-text-soft);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar__actions {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 10px;
}

.topbar__run {
  display: flex;
  max-width: 430px;
  min-width: 0;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border-accent);
  border-radius: 999px;
  background: var(--color-accent-soft);
  padding: 3px 4px 3px 9px;
}

.topbar__run-goal {
  overflow: hidden;
  max-width: 170px;
  color: var(--color-text-soft);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar__run-meta {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  white-space: nowrap;
}

.topbar__run-stop {
  border: 0;
  border-left: 1px solid var(--color-border-accent);
  background: transparent;
  padding: 1px 6px;
  color: var(--color-accent-strong);
  font-size: 10.5px;
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

@media (max-width: 1100px) {
  .topbar__run-goal {
    display: none;
  }
}
</style>
