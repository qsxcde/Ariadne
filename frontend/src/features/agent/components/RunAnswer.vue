<script setup lang="ts">
import { computed } from "vue";
import MarkdownContent from "@/shared/components/MarkdownContent.vue";
import SourceCitationList from "@/shared/components/SourceCitationList.vue";
import type { SourceRef } from "@/api";
import type { AgentRunViewModel } from "@/shared/types";

const props = defineProps<{
  run: AgentRunViewModel;
}>();

const emit = defineEmits<{
  selectSource: [source: SourceRef, index: number];
}>();

const isActive = computed(() =>
  ["planning", "tool_running", "answering", "running"].includes(props.run.status),
);
</script>

<template>
  <section class="run-answer">
    <p v-if="!run.answer && isActive" class="run-answer__pending">正在整理证据…</p>
    <MarkdownContent v-else-if="run.answer" :text="run.answer" />
    <p v-else-if="run.status === 'failed'" class="run-answer__error">
      {{ run.error || "研究失败，请重试。" }}
    </p>

    <p v-if="run.warning" class="run-answer__warning">{{ run.warning }}</p>

    <SourceCitationList
      v-if="run.sources.length"
      :sources="run.sources"
      @select="(source, index) => emit('selectSource', source, index)"
    />

    <p v-if="run.error && run.answer" class="run-answer__error">{{ run.error }}</p>
  </section>
</template>

<style scoped>
.run-answer {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding: 14px 16px;
}

.run-answer__pending {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.run-answer__warning {
  margin: 0;
  color: var(--color-accent-strong);
  font-size: 11px;
  line-height: 1.5;
}

.run-answer__error {
  margin: 0;
  color: var(--color-danger, #b4423a);
  font-size: 11.5px;
  line-height: 1.5;
}
</style>
