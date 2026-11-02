<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import { usePapers } from "../../../composables/usePapers";
import type { PaperSummary } from "../../../api";
import { formatUpdatedAt } from "../../../utils/format";

const emit = defineEmits<{
  open: [paperId: string];
  today: [];
  synthesis: [];
  feed: [];
  settings: [];
}>();

const {
  papers,
  collections,
  filters,
  isLoading,
  isUploading,
  errorMessage,
  paperCount,
  readingCount,
  loadLibrary,
  upload,
} = usePapers();

const fileInputRef = ref<HTMLInputElement | null>(null);

const STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "inbox", label: "待读" },
  { value: "queued", label: "队列中" },
  { value: "skimming", label: "速读" },
  { value: "reading", label: "在读" },
  { value: "read", label: "已读" },
  { value: "archived", label: "已归档" },
];

const STATUS_LABELS: Record<string, string> = {
  inbox: "待读",
  queued: "队列中",
  skimming: "速读",
  reading: "在读",
  read: "已读",
  archived: "已归档",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function statusClass(status: string): string {
  return `paper-card__status--${status}`;
}

function progressPercent(progress: number): number {
  return Math.round(Math.max(0, Math.min(1, progress)) * 100);
}

function openPaper(paper: PaperSummary): void {
  emit("open", paper.id);
}

function pickFiles(): void {
  fileInputRef.value?.click();
}

async function handleFiles(event: Event): Promise<void> {
  const target = event.target as HTMLInputElement;
  const files = Array.from(target.files ?? []);
  target.value = "";
  for (const file of files) {
    const paper = await upload(file);
    if (paper) {
      ElMessage.success(`已导入《${paper.title}》`);
    }
  }
}

onMounted(() => {
  void loadLibrary();
});
</script>

<template>
  <section class="paper-library" aria-label="文献库">
    <header class="paper-library__bar">
      <div>
        <p class="paper-library__eyebrow">文献库 · {{ paperCount }} 篇</p>
        <h1 class="paper-library__title">我的论文</h1>
        <p class="paper-library__subtitle">在读 {{ readingCount }} 篇 · 按状态、集合和标签整理阅读进度</p>
      </div>
      <div class="paper-library__actions">
        <button type="button" class="paper-library__text-button" @click="emit('today')">
          Today
        </button>
        <button type="button" class="paper-library__text-button" @click="emit('synthesis')">
          综合
        </button>
        <button type="button" class="paper-library__text-button" @click="emit('feed')">
          跟进
        </button>
        <button type="button" class="paper-library__text-button" @click="emit('settings')">
          设置
        </button>
        <button
          type="button"
          class="paper-library__upload"
          :disabled="isUploading"
          @click="pickFiles"
        >
          <UploadFilled class="paper-library__upload-icon" />
          {{ isUploading ? "上传中…" : "导入论文" }}
        </button>
      </div>
    </header>

    <input
      ref="fileInputRef"
      class="paper-library__file-input"
      type="file"
      accept=".pdf,application/pdf"
      multiple
      @change="handleFiles"
    />

    <div class="paper-library__filters">
      <input
        v-model="filters.query"
        class="paper-library__search"
        type="search"
        placeholder="搜索标题或作者…"
        @keyup.enter="loadLibrary"
      />
      <select v-model="filters.status" class="paper-library__select" @change="loadLibrary">
        <option v-for="option in STATUS_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
      <select v-model="filters.collectionId" class="paper-library__select" @change="loadLibrary">
        <option value="">全部集合</option>
        <option v-for="collection in collections" :key="collection.id" :value="collection.id">
          {{ collection.name }}（{{ collection.paper_count }}）
        </option>
      </select>
      <input
        v-model="filters.tag"
        class="paper-library__tag-input"
        type="text"
        placeholder="标签"
        @keyup.enter="loadLibrary"
      />
      <button type="button" class="paper-library__text-button" @click="loadLibrary">刷新</button>
    </div>

    <p v-if="errorMessage" class="paper-library__error">{{ errorMessage }}</p>
    <p v-if="isLoading && !papers.length" class="paper-library__state">正在读取文献库…</p>
    <div v-else-if="!papers.length" class="paper-library__empty">
      <p class="paper-library__empty-title">还没有收录论文</p>
      <p class="paper-library__empty-hint">点击「导入论文」上传 PDF，解析完成后会出现在这里。</p>
    </div>

    <div v-else class="paper-library__grid">
      <article
        v-for="paper in papers"
        :key="paper.id"
        class="paper-card"
        tabindex="0"
        role="button"
        @click="openPaper(paper)"
        @keyup.enter="openPaper(paper)"
      >
        <div class="paper-card__head">
          <span class="paper-card__status" :class="statusClass(paper.reading_status)">
            {{ statusLabel(paper.reading_status) }}
          </span>
          <span class="paper-card__updated">{{ formatUpdatedAt(paper.updated_at) }}</span>
        </div>
        <h2 class="paper-card__title">{{ paper.title }}</h2>
        <p class="paper-card__meta">
          <span v-if="(paper.authors ?? []).length">{{ (paper.authors ?? []).slice(0, 3).join("、") }}</span>
          <span v-if="paper.year"> · {{ paper.year }}</span>
          <span v-if="paper.venue"> · {{ paper.venue }}</span>
        </p>
        <div class="paper-card__progress" aria-hidden="true">
          <span class="paper-card__progress-fill" :style="{ width: `${progressPercent(paper.progress)}%` }" />
        </div>
        <div class="paper-card__foot">
          <span>{{ progressPercent(paper.progress) }}%</span>
          <div class="paper-card__tags">
            <span v-for="tag in paper.tags" :key="tag" class="paper-card__tag">{{ tag }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.paper-library {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 18px;
  padding: 28px 34px;
  overflow-y: auto;
  background: var(--color-bg);
}

.paper-library__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.paper-library__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.paper-library__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
  color: var(--color-text);
}

.paper-library__subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.paper-library__actions,
.paper-library__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.paper-library__upload,
.paper-library__text-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 13px;
  padding: 8px 12px;
}

.paper-library__upload {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: #fff;
}

.paper-library__upload:disabled {
  cursor: wait;
  opacity: 0.7;
}

.paper-library__upload-icon {
  width: 14px;
  height: 14px;
}

.paper-library__text-button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.paper-library__file-input {
  display: none;
}

.paper-library__filters {
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-panel);
}

.paper-library__search {
  min-width: 220px;
  flex: 1;
}

.paper-library__search,
.paper-library__select,
.paper-library__tag-input {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 13px;
  padding: 8px 10px;
}

.paper-library__tag-input {
  width: 110px;
}

.paper-library__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 13px;
}

.paper-library__state,
.paper-library__empty {
  padding: 48px 24px;
  border: 1px dashed var(--color-border);
  border-radius: 12px;
  color: var(--color-text-muted);
  text-align: center;
}

.paper-library__empty-title {
  margin: 0 0 8px;
  color: var(--color-text);
  font-size: 16px;
  font-weight: 600;
}

.paper-library__empty-hint {
  margin: 0;
  font-size: 13px;
}

.paper-library__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.paper-card {
  display: flex;
  min-height: 170px;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-panel);
  cursor: pointer;
  transition: border-color 0.15s ease, transform 0.15s ease;
}

.paper-card:hover,
.paper-card:focus-visible {
  border-color: var(--color-accent);
  outline: none;
  transform: translateY(-1px);
}

.paper-card__head,
.paper-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.paper-card__status {
  border-radius: 999px;
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-size: 11px;
  padding: 3px 8px;
}

.paper-card__status--reading {
  background: color-mix(in srgb, var(--color-accent) 12%, transparent);
  color: var(--color-accent);
}

.paper-card__status--read {
  background: color-mix(in srgb, var(--color-success, #2e7d32) 12%, transparent);
  color: var(--color-success, #2e7d32);
}

.paper-card__updated {
  color: var(--color-text-muted);
  font-size: 11px;
}

.paper-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 620;
  line-height: 1.35;
}

.paper-card__meta {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.4;
}

.paper-card__progress {
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-bg);
}

.paper-card__progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-accent);
}

.paper-card__foot {
  margin-top: auto;
  color: var(--color-text-muted);
  font-size: 11px;
}

.paper-card__tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.paper-card__tag {
  border-radius: 4px;
  background: var(--color-bg);
  padding: 2px 5px;
}
</style>
