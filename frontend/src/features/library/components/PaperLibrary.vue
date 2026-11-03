<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { UploadFilled } from "@element-plus/icons-vue";
import StateBlock from "../../../components/StateBlock.vue";
import LibraryTable from "./LibraryTable.vue";
import PaperImportDialog from "./PaperImportDialog.vue";
import { usePapers } from "../../../composables/usePapers";
import { exportBibtex } from "../../../api/papers";

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
  saveReadingState,
  upload,
} = usePapers();

const route = useRoute();
const router = useRouter();
const fileInputRef = ref<HTMLInputElement | null>(null);
const isImportDialogOpen = ref(false);

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "inbox", label: "待读" },
  { value: "queued", label: "队列" },
  { value: "skimming", label: "速读" },
  { value: "reading", label: "在读" },
  { value: "read", label: "已读" },
  { value: "archived", label: "归档" },
];

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
      ElMessage.success("已导入《" + paper.title + "》");
    }
  }
}

async function handleImported(): Promise<void> {
  await loadLibrary();
}

async function downloadBibtex(): Promise<void> {
  try {
    const bib = await exportBibtex();
    const blob = new Blob([bib], { type: "application/x-bibtex;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "scipal-library.bib";
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "导出 BibTeX 失败");
  }
}

function selectStatus(value: string): void {
  filters.value.status = value;
  void loadLibrary();
}

function markRead(paperId: string): void {
  void saveReadingState(paperId, { reading_status: "read" });
}

/** Rail/TopBar 通过 query 传入搜索、集合与导入意图。 */
function applyRouteQuery(reload: boolean): void {
  filters.value.query = typeof route.query.q === "string" ? route.query.q : "";
  filters.value.collectionId =
    typeof route.query.collection === "string" ? route.query.collection : "";

  if (route.query.import === "1") {
    isImportDialogOpen.value = true;
    const next = { ...route.query };
    delete next.import;
    void router.replace({ name: "library", query: next });
  }

  if (reload && (filters.value.query || filters.value.collectionId)) {
    void loadLibrary();
  }
}

onMounted(() => {
  applyRouteQuery(false);
  void loadLibrary();
});

watch(
  () => route.query,
  () => applyRouteQuery(true),
);
</script>

<template>
  <section class="paper-library" aria-label="文献库">
    <header class="paper-library__bar">
      <div>
        <p class="paper-library__eyebrow">文献库 · {{ paperCount }} 篇</p>
        <h1 class="paper-library__title">我的论文</h1>
        <p class="paper-library__subtitle">
          在读 {{ readingCount }} 篇 · 按状态、集合和标签整理阅读进度
        </p>
      </div>
      <div class="paper-library__actions">
        <button type="button" class="paper-library__text-button" @click="downloadBibtex">
          导出 BibTeX
        </button>
        <button
          type="button"
          class="paper-library__text-button"
          @click="isImportDialogOpen = true"
        >
          按标识导入
        </button>
        <button
          type="button"
          class="paper-library__upload"
          :disabled="isUploading"
          @click="pickFiles"
        >
          <UploadFilled class="paper-library__upload-icon" />
          {{ isUploading ? "上传中…" : "上传 PDF" }}
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

    <PaperImportDialog
      :visible="isImportDialogOpen"
      @close="isImportDialogOpen = false"
      @imported="handleImported"
    />

    <div class="paper-library__toolbar">
      <div class="paper-library__statuses" role="group" aria-label="阅读状态">
        <button
          v-for="option in STATUS_OPTIONS"
          :key="option.value"
          type="button"
          class="paper-library__status"
          :class="{ 'is-active': filters.status === option.value }"
          @click="selectStatus(option.value)"
        >
          {{ option.label }}
        </button>
      </div>

      <div class="paper-library__controls">
        <input
          v-model="filters.query"
          class="paper-library__search"
          type="search"
          placeholder="搜索标题或作者…"
          @keyup.enter="loadLibrary"
        />
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
        <button type="button" class="paper-library__text-button" @click="loadLibrary">
          刷新
        </button>
      </div>
    </div>

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取文献库失败"
      :description="errorMessage"
      action-label="重试"
      @action="loadLibrary"
    />

    <template v-else>
      <StateBlock
        v-if="isLoading && !papers.length"
        kind="loading"
        description="正在读取文献库…"
      />
      <StateBlock
        v-else-if="!papers.length"
        kind="empty"
        title="还没有收录论文"
        description="上传本地 PDF，或从 arXiv / DOI / 网页抓取题录。"
      >
        <template #actions>
          <button type="button" class="paper-library__upload" @click="pickFiles">
            上传 PDF
          </button>
          <button
            type="button"
            class="paper-library__text-button"
            @click="isImportDialogOpen = true"
          >
            按标识导入
          </button>
        </template>
      </StateBlock>
      <LibraryTable
        v-else
        :papers="papers"
        @open="emit('open', $event)"
        @mark-read="markRead"
      />
    </template>
  </section>
</template>

<style scoped>
.paper-library {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 14px;
  padding: 24px 28px 0;
  overflow: hidden;
  background: var(--color-page);
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

.paper-library__actions,
.paper-library__controls,
.paper-library__statuses {
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

.paper-library__file-input {
  display: none;
}

.paper-library__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 10px;
}

.paper-library__status {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 5px 2px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-library__status + .paper-library__status {
  margin-left: 10px;
}

.paper-library__status.is-active {
  border-bottom-color: var(--color-accent);
  color: var(--color-text);
  font-weight: 600;
}

.paper-library__search {
  min-width: 200px;
  flex: 1;
}

.paper-library__search,
.paper-library__select,
.paper-library__tag-input {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
}

.paper-library__tag-input {
  width: 100px;
}

.paper-library__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
}

.paper-library__state,
.paper-library__empty {
  padding: 64px 24px;
  color: var(--color-text-muted);
  text-align: center;
}

.paper-library__empty-title {
  margin: 0 0 8px;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
}

.paper-library__empty-hint {
  margin: 0;
  font-size: 12px;
}

.paper-library__empty-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
}
</style>
