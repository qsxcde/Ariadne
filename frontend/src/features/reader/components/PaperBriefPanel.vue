<script setup lang="ts">
import { computed } from "vue";
import { ElMessage } from "element-plus";

import { usePapers } from "@/features/library/composables/usePapers";

const props = defineProps<{
  paperId: string;
}>();

const emit = defineEmits<{
  jumpSection: [title: string];
}>();

const { brief, isBriefLoading, loadBrief } = usePapers();

const currentBrief = computed(() =>
  brief.value?.paper_id === props.paperId ? brief.value : null,
);

async function generateBrief(): Promise<void> {
  await loadBrief(props.paperId, Boolean(currentBrief.value));
  if (brief.value) {
    ElMessage.success("速读卡已生成");
  }
}
</script>

<template>
  <section class="paper-workspace__brief">
    <header class="paper-workspace__brief-head">
      <span class="paper-workspace__eyebrow">5 分钟速读</span>
      <button
        type="button"
        class="paper-workspace__secondary"
        :class="{ 'paper-workspace__secondary--primary': !currentBrief }"
        :disabled="isBriefLoading"
        @click="generateBrief"
      >
        {{ isBriefLoading ? "生成中…" : currentBrief ? "重新生成" : "生成速读卡" }}
      </button>
    </header>
    <p v-if="!currentBrief" class="paper-workspace__empty">
      基于章节摘要生成 TL;DR、贡献、方法、实验与局限，每条结论带原文引用。
    </p>
    <div v-else class="paper-workspace__brief-body">
      <p class="paper-workspace__tldr">{{ currentBrief.tldr }}</p>
      <div v-if="(currentBrief.contributions ?? []).length">
        <h3>贡献</h3>
        <ul class="paper-workspace__brief-list">
          <li v-for="item in currentBrief.contributions ?? []" :key="item">{{ item }}</li>
        </ul>
      </div>
      <p><strong>方法：</strong>{{ currentBrief.method }}</p>
      <p><strong>实验：</strong>{{ currentBrief.experiments }}</p>
      <p><strong>局限：</strong>{{ currentBrief.limitations }}</p>
      <div v-if="(currentBrief.takeaways ?? []).length">
        <h3>阅读要点</h3>
        <ul class="paper-workspace__brief-list">
          <li v-for="item in currentBrief.takeaways ?? []" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div v-if="(currentBrief.sections ?? []).length">
        <h3>章节摘要</h3>
        <ul class="paper-workspace__section-list">
          <li v-for="section in currentBrief.sections ?? []" :key="section.title">
            <button
              type="button"
              class="paper-workspace__section"
              @click="emit('jumpSection', section.title)"
            >
              <span class="paper-workspace__section-title">{{ section.title }}</span>
              <span class="paper-workspace__section-summary">{{ section.summary }}</span>
              <span v-if="(section.chunk_indexes ?? []).length" class="paper-workspace__chunks">
                <span class="paper-workspace__chunks-label">引用</span>
                <span
                  v-for="index in section.chunk_indexes"
                  :key="index"
                  class="paper-workspace__chunk"
                >
                  #{{ index + 1 }}
                </span>
              </span>
            </button>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.paper-workspace__eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.paper-workspace__brief {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.paper-workspace__brief-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.paper-workspace__brief-body {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.paper-workspace__brief-body h3 {
  margin: 10px 0 4px;
  color: var(--color-text);
  font-size: 12px;
}

.paper-workspace__brief-body p {
  margin: 0 0 6px;
}

.paper-workspace__tldr {
  color: var(--color-text);
  font-size: 13px !important;
  font-weight: 600;
}

.paper-workspace__brief-list {
  margin: 0 0 6px;
  padding-left: 18px;
}

.paper-workspace__section-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 0 0 6px;
  padding: 0;
  list-style: none;
}

.paper-workspace__section {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  text-align: left;
  cursor: pointer;
}

.paper-workspace__section:hover {
  border-color: var(--color-accent);
}

.paper-workspace__section-title {
  color: var(--color-text);
  font-size: 12px;
  font-weight: 600;
}

.paper-workspace__section-summary {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.paper-workspace__chunks {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 1px;
}

.paper-workspace__chunks-label {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.06em;
}

.paper-workspace__chunk {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  padding: 0 4px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.paper-workspace__empty {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
</style>
