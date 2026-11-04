<script setup lang="ts">
import { ref, watch } from "vue";
import ToolStepRow from "@/features/agent/components/ToolStepRow.vue";
import type { SourceRef } from "@/api";
import type { AgentStepViewModel } from "@/shared/types";

const props = defineProps<{
  steps: AgentStepViewModel[];
  active: boolean;
}>();

const emit = defineEmits<{
  selectSource: [source: SourceRef, index: number];
}>();

const expanded = ref(props.active);

watch(
  () => props.active,
  (active) => {
    expanded.value = active;
  },
);
</script>

<template>
  <section v-if="steps.length" class="run-timeline">
    <button
      type="button"
      class="run-timeline__toggle"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span>{{ expanded ? "收起过程" : "展开过程" }}</span>
      <span class="run-timeline__count">{{ steps.length }} 步</span>
    </button>
    <ol v-if="expanded" class="run-timeline__list">
      <ToolStepRow
        v-for="step in steps"
        :key="step.step"
        :step="step"
        @select-source="(source, index) => emit('selectSource', source, index)"
      />
    </ol>
  </section>
</template>

<style scoped>
.run-timeline {
  border-bottom: 1px solid var(--color-border);
  padding: 10px 16px 8px;
}

.run-timeline__toggle {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 11px;
  text-align: left;
}

.run-timeline__toggle:hover {
  color: var(--color-text);
}

.run-timeline__count {
  font-family: var(--font-mono);
  font-size: 10px;
}

.run-timeline__list {
  margin: 6px 0 0;
  padding: 0;
  list-style: none;
}
</style>
