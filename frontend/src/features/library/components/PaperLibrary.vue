<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Search, UploadFilled } from "@element-plus/icons-vue";
import StateBlock from "../../../components/StateBlock.vue";
import LibraryTable from "./LibraryTable.vue";
import PaperImportDialog from "./PaperImportDialog.vue";
import { usePapers } from "../../../composables/usePapers";
import { exportBibtex } from "../../../api/papers";
import { addPaperToCollection, createCollection } from "../../../api/collections";

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
const selectedIndex = ref(0);
const checkedIds = ref<string[]>([]);
const bulkCollectionId = ref("");
const isBulkBusy = ref(false);
const selectedPaperId = computed(() => papers.value[selectedIndex.value]?.id ?? "");

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

function toggleCheck(paperId: string): void {
  checkedIds.value = checkedIds.value.includes(paperId)
    ? checkedIds.value.filter((id) => id !== paperId)
    : [...checkedIds.value, paperId];
}

function toggleAll(): void {
  checkedIds.value =
    checkedIds.value.length === papers.value.length
      ? []
      : papers.value.map((paper) => paper.id);
}

function clearChecked(): void {
  checkedIds.value = [];
  bulkCollectionId.value = "";
}

async function markCheckedRead(): Promise<void> {
  if (!checkedIds.value.length) return;
  isBulkBusy.value = true;
  const ids = [...checkedIds.value];
  for (const paperId of ids) {
    await saveReadingState(paperId, { reading_status: "read" });
  }
  await loadLibrary();
  clearChecked();
  isBulkBusy.value = false;
  ElMessage.success(`已将 ${ids.length} 篇标记为已读`);
}

async function addCheckedToCollection(): Promise<void> {
  if (!bulkCollectionId.value || !checkedIds.value.length) return;
  isBulkBusy.value = true;
  const collectionId = bulkCollectionId.value;
  const ids = [...checkedIds.value];
  try {
    await Promise.all(ids.map((paperId) => addPaperToCollection(collectionId, paperId)));
    await loadLibrary();
    ElMessage.success(`已加入 ${ids.length} 篇论文`);
    clearChecked();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加入集合失败");
  } finally {
    isBulkBusy.value = false;
  }
}

async function createNewCollection(): Promise<void> {
  let result;
  try {
    result = await ElMessageBox.prompt("给集合起一个便于检索的名字。", "新建集合", {
      confirmButtonText: "创建",
      cancelButtonText: "取消",
      inputPlaceholder: "例如：RAG 主线",
      inputValidator: (value) => (value?.trim() ? true : "集合名称不能为空"),
    });
  } catch {
    return;
  }
  const name = result.value.trim();
  try {
    const collection = await createCollection({ name });
    const ids = [...checkedIds.value];
    if (ids.length) {
      await Promise.all(
        ids.map((paperId) => addPaperToCollection(collection.id, paperId)),
      );
    }
    await loadLibrary();
    filters.value.collectionId = collection.id;
    await loadLibrary();
    clearChecked();
    ElMessage.success(
      ids.length
        ? `已创建「${collection.name}」并加入 ${ids.length} 篇`
        : `已创建「${collection.name}」`,
    );
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建集合失败");
  }
}

function scrollToSelection(): void {
  void nextTick(() => {
    window.document
      .querySelector(".library-table__row.is-selected")
      ?.scrollIntoView({ block: "nearest" });
  });
}

function moveSelection(delta: number): void {
  if (!papers.value.length) {
    return;
  }
  selectedIndex.value = Math.max(
    0,
    Math.min(papers.value.length - 1, selectedIndex.value + delta),
  );
  scrollToSelection();
}

function handleKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey || !papers.value.length) {
    return;
  }
  const key = event.key.toLowerCase();
  const paper = papers.value[selectedIndex.value];
  if (key === "j" || key === "k") {
    event.preventDefault();
    moveSelection(key === "j" ? 1 : -1);
    return;
  }
  if (event.key === "Enter" && paper) {
    event.preventDefault();
    emit("open", paper.id);
    return;
  }
  if (key === "s" && paper && paper.reading_status !== "read") {
    event.preventDefault();
    markRead(paper.id);
  }
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
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});

watch(
  () => route.query,
  () => applyRouteQuery(true),
);

watch(
  () => papers.value.map((paper) => paper.id).join("|"),
  () => {
    selectedIndex.value = Math.min(
      selectedIndex.value,
      Math.max(0, papers.value.length - 1),
    );
    const visible = new Set(papers.value.map((paper) => paper.id));
    checkedIds.value = checkedIds.value.filter((id) => visible.has(id));
  },
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
        <label class="paper-library__search-wrap">
          <Search class="paper-library__search-icon" />
          <input
            v-model="filters.query"
            class="paper-library__search"
            type="search"
            placeholder="搜索标题或作者…"
            @keyup.enter="loadLibrary"
          />
        </label>
        <select v-model="filters.collectionId" class="paper-library__select" @change="loadLibrary">
          <option value="">全部集合</option>
          <option v-for="collection in collections" :key="collection.id" :value="collection.id">
            {{ collection.name }}（{{ collection.paper_count }}）
          </option>
        </select>
        <button type="button" class="paper-library__text-button" @click="createNewCollection">
          <Plus class="paper-library__button-icon" /> 新建集合
        </button>
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
        <span class="paper-library__hint">J/K 移动 · Enter 打开 · S 已读</span>
      </div>
    </div>

    <div v-if="checkedIds.length" class="paper-library__bulk">
      <span class="paper-library__bulk-count">已选 {{ checkedIds.length }} 篇</span>
      <div class="paper-library__bulk-actions">
        <button type="button" :disabled="isBulkBusy" @click="markCheckedRead">
          标记已读
        </button>
        <select v-model="bulkCollectionId" class="paper-library__select">
          <option value="">加入集合…</option>
          <option v-for="collection in collections" :key="collection.id" :value="collection.id">
            {{ collection.name }}
          </option>
        </select>
        <button
          type="button"
          :disabled="!bulkCollectionId || isBulkBusy"
          @click="addCheckedToCollection"
        >
          加入
        </button>
        <button type="button" class="paper-library__bulk-clear" @click="clearChecked">
          清除选择
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
        :selected-id="selectedPaperId"
        :checked-ids="checkedIds"
        @open="emit('open', $event)"
        @mark-read="markRead"
        @check="toggleCheck"
        @check-all="toggleAll"
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
  padding: 24px max(28px, calc((100% - 1400px) / 2)) 0;
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

.paper-library__controls {
  flex: 1 1 560px;
  justify-content: flex-end;
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

.paper-library__upload-icon,
.paper-library__button-icon {
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
  border-bottom-color: var(--color-text);
  color: var(--color-text);
  font-weight: 600;
}

.paper-library__search-wrap {
  position: relative;
  display: flex;
  min-width: 210px;
  flex: 1 1 240px;
  align-items: center;
}

.paper-library__search-icon {
  position: absolute;
  left: 9px;
  width: 13px;
  color: var(--color-text-muted);
  pointer-events: none;
}

.paper-library__search {
  width: 100%;
  min-width: 0;
  padding-left: 28px;
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

.paper-library__hint {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.paper-library__bulk {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  border: 1px solid var(--color-border);
  border-left: 2px solid var(--color-accent);
  background: var(--color-surface-alt);
  padding: 7px 10px;
}

.paper-library__bulk-count {
  color: var(--color-text);
  font-size: 11px;
  font-weight: 600;
}

.paper-library__bulk-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.paper-library__bulk-actions button {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 4px 9px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.paper-library__bulk-actions button:hover:not(:disabled) {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.paper-library__bulk-actions button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.paper-library__bulk-actions .paper-library__select {
  padding: 4px 8px;
  font-size: 11px;
}

.paper-library__bulk-clear {
  border-color: transparent !important;
  background: transparent !important;
  color: var(--color-text-muted) !important;
}

@media (max-width: 1320px) {
  .paper-library__hint {
    display: none;
  }
}

@media (max-width: 1100px) {
  .paper-library__toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }

  .paper-library__controls {
    flex: 0 0 auto;
    justify-content: flex-start;
  }
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
