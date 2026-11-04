<script setup lang="ts">
import { computed } from "vue";
import type { SourceRef } from "@/api";
import type { AgentStepViewModel } from "@/shared/types";

const props = defineProps<{
  step: AgentStepViewModel;
}>();

const emit = defineEmits<{
  selectSource: [source: SourceRef, index: number];
}>();

const TOOL_LABELS: Record<string, string> = {
  search_session_chunks: "检索片段",
  read_chunk: "读取片段",
  get_paper: "论文信息",
};

const STATUS_LABELS: Record<AgentStepViewModel["status"], string> = {
  running: "进行中",
  ok: "完成",
  error: "失败",
  interrupted: "已中断",
};

const toolLabel = computed(() => TOOL_LABELS[props.step.tool] ?? props.step.tool);

const argumentSummary = computed(() => {
  const args = props.step.arguments;
  if (!args) {
    return "";
  }
  if (typeof args.query === "string") {
    return args.query;
  }
  if (typeof args.section === "string" && typeof args.chunk_index === "number") {
    return `${args.section} · #${args.chunk_index}`;
  }
  if (typeof args.paper_id === "string") {
    return args.paper_id;
  }
  return Object.keys(args).join(" · ");
});

const durationLabel = computed(() => {
  if (props.step.finishedAt === undefined) {
    return "";
  }
  const seconds = (props.step.finishedAt - props.step.startedAt) / 1000;
  return seconds < 1 ? "<1s" : `${Math.round(seconds)}s`;
});

const statusLabel = computed(() => STATUS_LABELS[props.step.status]);
</script>

<template>
  <li class="tool-step" :class="`tool-step--${step.status}`">
    <span class="tool-step__index">{{ String(step.step).padStart(2, "0") }}</span>
    <div class="tool-step__main">
      <div class="tool-step__row">
        <span class="tool-step__tool">{{ toolLabel }}</span>
        <span v-if="argumentSummary" class="tool-step__args">{{ argumentSummary }}</span>
        <span class="tool-step__spacer" />
        <span v-if="durationLabel" class="tool-step__duration">{{ durationLabel }}</span>
        <span class="tool-step__status">{{ statusLabel }}</span>
      </div>
      <p v-if="step.summary && step.status !== 'running'" class="tool-step__summary">
        {{ step.summary }}
      </p>
      <p v-if="step.error" class="tool-step__error">{{ step.error }}</p>
      <ul v-if="step.sources.length" class="tool-step__sources">
        <li v-for="(source, index) in step.sources.slice(0, 3)" :key="`${source.section}#${source.chunk_index}`">
          <button
            type="button"
            class="tool-step__source"
            :title="source.text_excerpt || source.section"
            @click="emit('selectSource', source, index)"
          >
            {{ source.section }} · #{{ source.chunk_index }}
          </button>
        </li>
        <li v-if="step.sources.length > 3" class="tool-step__more">
          +{{ step.sources.length - 3 }}
        </li>
      </ul>
    </div>
  </li>
</template>

<style scoped>
.tool-step {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  border-top: 1px solid var(--color-border);
  padding: 8px 0;
}

.tool-step:first-child {
  border-top: 0;
}

.tool-step__index {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.8;
}

.tool-step__main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.tool-step__row {
  display: flex;
  min-width: 0;
  align-items: baseline;
  gap: 7px;
}

.tool-step__tool {
  flex: 0 0 auto;
  color: var(--color-text);
  font-size: 12px;
  font-weight: 600;
}

.tool-step__args {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-step__spacer {
  flex: 1;
}

.tool-step__duration,
.tool-step__status {
  flex: 0 0 auto;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.tool-step--running .tool-step__status {
  color: var(--color-accent);
}

.tool-step--error .tool-step__status {
  color: var(--color-danger, #b4423a);
}

.tool-step__summary {
  margin: 0;
  color: var(--color-text-soft);
  font-size: 11px;
  line-height: 1.5;
}

.tool-step__error {
  margin: 0;
  color: var(--color-danger, #b4423a);
  font-size: 11px;
  line-height: 1.5;
}

.tool-step__sources {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 2px 0 0;
  padding: 0;
  list-style: none;
}

.tool-step__source {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: transparent;
  padding: 1px 5px;
  color: var(--color-text-muted);
  font-size: 10px;
}

.tool-step__source:hover {
  border-color: var(--color-border-accent);
  color: var(--color-accent-strong);
}

.tool-step__more {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 1.7;
}
</style>
