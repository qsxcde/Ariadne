<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import RunStatusBadge from "@/features/agent/components/RunStatusBadge.vue";
import type { AgentRunViewModel } from "@/shared/types";

const props = defineProps<{
  run: AgentRunViewModel;
  focused: boolean;
}>();

const emit = defineEmits<{
  stop: [];
  focus: [];
}>();

const now = ref(Date.now());
let ticker: number | null = null;

onMounted(() => {
  ticker = window.setInterval(() => {
    if (!props.run.finishedAt) {
      now.value = Date.now();
    }
  }, 1000);
});

onBeforeUnmount(() => {
  if (ticker !== null) {
    window.clearInterval(ticker);
  }
});

const isActive = computed(() =>
  ["planning", "tool_running", "answering", "running"].includes(props.run.status),
);

const elapsedSeconds = computed(() => {
  const end = props.run.finishedAt ?? (now.value || Date.now());
  return Math.max(0, Math.round((end - props.run.createdAt) / 1000));
});

const elapsedLabel = computed(() => {
  const total = elapsedSeconds.value;
  if (total < 60) {
    return `${total}s`;
  }
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
});
</script>

<template>
  <header class="run-header">
    <div class="run-header__row">
      <span class="run-header__eyebrow">研究</span>
      <RunStatusBadge :status="run.status" />
      <span class="run-header__meta">
        <span>{{ elapsedLabel }}</span>
        <span v-if="run.steps.length">· {{ run.steps.length }} 步</span>
      </span>
      <span class="run-header__spacer" />
      <button
        v-if="isActive"
        type="button"
        class="run-header__action"
        @click="emit('stop')"
      >
        停止
      </button>
      <button
        type="button"
        class="run-header__action run-header__action--quiet"
        :aria-pressed="focused"
        @click="emit('focus')"
      >
        {{ focused ? "退出专注" : "专注" }}
      </button>
    </div>
    <p class="run-header__goal">{{ run.goal }}</p>
  </header>
</template>

<style scoped>
.run-header {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: 1px solid var(--color-border);
  padding: 12px 16px 10px;
}

.run-header__row {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
}

.run-header__eyebrow {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.run-header__meta {
  display: inline-flex;
  gap: 4px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.run-header__spacer {
  flex: 1;
}

.run-header__action {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  padding: 3px 8px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.run-header__action:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.run-header__action--quiet {
  border-color: transparent;
  color: var(--color-text-muted);
}

.run-header__goal {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}
</style>
