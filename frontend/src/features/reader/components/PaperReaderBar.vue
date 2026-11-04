<script setup lang="ts">
import { Close, Tickets } from "@element-plus/icons-vue";

import type { PaperContent } from "../../../api";

defineProps<{
  content: PaperContent | null;
  viewMode: "text" | "pdf";
  outlineVisible: boolean;
  showClose: boolean;
}>();

const emit = defineEmits<{
  setViewMode: [mode: "text" | "pdf"];
  toggleOutline: [];
  close: [];
}>();
</script>

<template>
  <header class="paper-reader__bar">
    <div class="paper-reader__meta">
      <p class="paper-reader__eyebrow">
        原文<span v-if="content?.parser_name"> · {{ content.parser_name }}</span>
        <span v-if="content?.chunk_count"> · {{ content.chunk_count }} 个片段</span>
      </p>
      <h1 class="paper-reader__filename">{{ content?.filename || "正在载入正文" }}</h1>
    </div>
    <div class="paper-reader__actions">
      <div class="paper-reader__modes" role="group" aria-label="原文视图">
        <button
          type="button"
          class="paper-reader__mode"
          :class="{ 'is-active': viewMode === 'text' }"
          @click="emit('setViewMode', 'text')"
        >
          正文
        </button>
        <button
          type="button"
          class="paper-reader__mode"
          :class="{ 'is-active': viewMode === 'pdf' }"
          @click="emit('setViewMode', 'pdf')"
        >
          原页
        </button>
      </div>
      <el-button
        class="paper-reader__toggle"
        :class="{ 'is-active': outlineVisible }"
        :icon="Tickets"
        text
        size="small"
        aria-label="切换目录"
        @click="emit('toggleOutline')"
      />
      <el-button
        v-if="showClose"
        class="paper-reader__close"
        :icon="Close"
        circle
        text
        aria-label="收起原文"
        @click="emit('close')"
      />
    </div>
  </header>
</template>

<style scoped>
.paper-reader__bar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  justify-content: space-between;
  padding: 14px 24px 12px;
  border-bottom: 1px solid var(--color-border);
}

.paper-reader__meta {
  min-width: 0;
}

.paper-reader__eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.02em;
}

.paper-reader__filename {
  margin: 0;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-reader__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 2px;
}

.paper-reader__toggle.is-active {
  color: var(--color-text);
  background: var(--color-surface-alt);
}

.paper-reader__modes {
  display: flex;
  padding: 2px;
  background: var(--color-surface-alt);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.paper-reader__mode {
  padding: 3px 10px;
  color: var(--color-text-muted);
  font-size: 11px;
  background: none;
  border: 0;
  border-radius: var(--radius-xs);
}

.paper-reader__mode.is-active {
  color: var(--color-text);
  background: var(--color-surface);
  box-shadow: 0 1px 2px rgba(60, 50, 35, 0.08);
}

@media (max-width: 1180px) {
  .paper-reader__bar {
    align-items: center;
    padding: 8px 16px;
  }

  .paper-reader__meta {
    display: none;
  }

  .paper-reader__actions {
    margin-left: auto;
  }
}
</style>
