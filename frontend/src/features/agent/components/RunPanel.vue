<script setup lang="ts">
import { computed, watch } from "vue";
import RunAnswer from "@/features/agent/components/RunAnswer.vue";
import RunComposer from "@/features/agent/components/RunComposer.vue";
import RunHeader from "@/features/agent/components/RunHeader.vue";
import RunTimeline from "@/features/agent/components/RunTimeline.vue";
import { useAgentRuns } from "@/features/agent/composables/useAgentRuns";
import { useSourcePreview } from "@/shared/composables/useSourcePreview";
import type { SourceRef } from "@/api";
import type { AgentRunViewModel } from "@/shared/types";

const props = defineProps<{
  run: AgentRunViewModel | null;
  sessionId: string;
  paperId: string;
  focused: boolean;
}>();

const emit = defineEmits<{
  focus: [];
}>();

const { startRun, stopRun } = useAgentRuns();
const { openCitation, setActiveSession } = useSourcePreview();

const isActive = computed(
  () =>
    props.run !== null &&
    ["planning", "tool_running", "answering", "running"].includes(props.run.status),
);

const SUGGESTIONS = ["总结方法与实验设置", "这篇的局限和失败案例", "关键数字与数据集出处"];

watch(
  () => props.sessionId,
  (sessionId) => setActiveSession(sessionId),
  { immediate: true },
);

function submit(goal: string): void {
  startRun({ sessionId: props.sessionId, goal, paperId: props.paperId });
}

function stop(): void {
  if (props.run) {
    stopRun(props.run.localId);
  }
}

function handleSource(source: SourceRef, index: number): void {
  void openCitation(source, index);
}
</script>

<template>
  <div class="run-panel">
    <RunHeader
      v-if="run"
      :run="run"
      :focused="focused"
      @stop="stop"
      @focus="emit('focus')"
    />

    <div v-else class="run-panel__intro">
      <p class="run-panel__lead">跨章节核对、对比与追问。</p>
      <div class="run-panel__suggestions">
        <button
          v-for="suggestion in SUGGESTIONS"
          :key="suggestion"
          type="button"
          class="run-panel__suggestion"
          @click="submit(suggestion)"
        >
          {{ suggestion }}
        </button>
      </div>
    </div>

    <RunTimeline
      v-if="run"
      :steps="run.steps"
      :active="isActive"
      @select-source="handleSource"
    />
    <RunAnswer v-if="run" :run="run" @select-source="handleSource" />

    <RunComposer
      :running="isActive"
      :has-run="run !== null"
      @submit="submit"
      @stop="stop"
    />
  </div>
</template>

<style scoped>
.run-panel {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
}

.run-panel__intro {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  padding: 20px 16px;
}

.run-panel__lead {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.run-panel__suggestions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.run-panel__suggestion {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: transparent;
  padding: 5px 9px;
  color: var(--color-text-soft);
  font-size: 11.5px;
  text-align: left;
}

.run-panel__suggestion:hover {
  border-color: var(--color-border-accent);
  background: var(--color-accent-soft);
  color: var(--color-accent-strong);
}
</style>
