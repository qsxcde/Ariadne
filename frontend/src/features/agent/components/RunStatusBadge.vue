<script setup lang="ts">
import { computed } from "vue";
import type { AgentRunStatus } from "@/shared/types";

const props = defineProps<{
  status: AgentRunStatus;
  compact?: boolean;
}>();

const LABELS: Record<AgentRunStatus, string> = {
  planning: "规划中",
  tool_running: "检索中",
  answering: "生成中",
  running: "运行中",
  completed: "已完成",
  failed: "已失败",
  stopped: "已停止",
};

const label = computed(() => LABELS[props.status]);
</script>

<template>
  <span class="run-status" :class="[`run-status--${status}`, { 'run-status--compact': compact }]">
    <span class="run-status__dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>

<style scoped>
.run-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.run-status--compact {
  gap: 4px;
  font-size: 10.5px;
}

.run-status__dot {
  width: 5px;
  height: 5px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
}

.run-status--planning,
.run-status--tool_running,
.run-status--answering,
.run-status--running {
  color: var(--color-accent);
}

.run-status--completed {
  color: var(--color-success, #2f7d63);
}

.run-status--failed {
  color: var(--color-danger, #b4423a);
}

.run-status--stopped {
  color: var(--color-text-muted);
}
</style>
