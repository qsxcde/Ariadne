<script setup lang="ts">
import { UploadFilled } from "@element-plus/icons-vue";

defineProps<{
  paperCount: number;
  readingCount: number;
  isUploading: boolean;
}>();

const emit = defineEmits<{
  exportBibtex: [];
  openImport: [];
  pickFiles: [];
}>();
</script>

<template>
  <header class="paper-library__bar">
    <div>
      <p class="paper-library__eyebrow">文献库 · {{ paperCount }} 篇</p>
      <h1 class="paper-library__title">我的论文</h1>
      <p class="paper-library__subtitle">
        在读 {{ readingCount }} 篇 · 按状态、集合和标签整理阅读进度
      </p>
    </div>
    <div class="paper-library__actions">
      <button type="button" class="paper-library__text-button" @click="emit('exportBibtex')">
        导出 BibTeX
      </button>
      <button type="button" class="paper-library__text-button" @click="emit('openImport')">
        按标识导入
      </button>
      <button
        type="button"
        class="paper-library__upload"
        :disabled="isUploading"
        @click="emit('pickFiles')"
      >
        <UploadFilled class="paper-library__upload-icon" />
        {{ isUploading ? "上传中…" : "上传 PDF" }}
      </button>
    </div>
  </header>
</template>

<style scoped>
.paper-library__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.paper-library__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.paper-library__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 27px;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.paper-library__subtitle {
  margin: 6px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-library__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-library__upload,
.paper-library__text-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 11px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.paper-library__upload {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: var(--color-white);
}

.paper-library__upload:disabled {
  cursor: wait;
  opacity: 0.7;
}

.paper-library__upload-icon {
  width: 13px;
  height: 13px;
}

.paper-library__text-button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
</style>
