<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import StateBlock from "@/shared/components/StateBlock.vue";
import LibraryBulkBar from "@/pages/library/LibraryBulkBar.vue";
import LibraryHeader from "@/pages/library/LibraryHeader.vue";
import LibraryTable from "@/features/library/components/LibraryTable.vue";
import LibraryToolbar from "@/pages/library/LibraryToolbar.vue";
import PaperImportDialog from "@/features/library/components/PaperImportDialog.vue";
import { usePapers } from "@/features/library/composables/usePapers";
import { exportBibtex } from "@/api/papers";
import { addPaperToCollection, createCollection } from "@/api/collections";

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
  remove,
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

async function removePaper(paperId: string): Promise<void> {
  const paper = papers.value.find((item) => item.id === paperId);
  if (!paper) return;
  try {
    await ElMessageBox.confirm(
      `删除《${paper.title}》后不可恢复，笔记、分块与索引会一并清理。`,
      "删除论文",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  const removed = await remove(paperId);
  if (removed) {
    checkedIds.value = checkedIds.value.filter((id) => id !== paperId);
    ElMessage.success("已删除");
  }
}

async function removeChecked(): Promise<void> {
  if (!checkedIds.value.length) return;
  const count = checkedIds.value.length;
  try {
    await ElMessageBox.confirm(
      `删除所选 ${count} 篇论文后不可恢复，笔记、分块与索引会一并清理。`,
      "批量删除",
      { type: "warning", confirmButtonText: "删除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }
  isBulkBusy.value = true;
  const ids = [...checkedIds.value];
  let failed = 0;
  for (const paperId of ids) {
    const removed = await remove(paperId);
    if (!removed) failed += 1;
  }
  clearChecked();
  isBulkBusy.value = false;
  if (failed) {
    ElMessage.error(`${failed} 篇删除失败`);
  } else {
    ElMessage.success(`已删除 ${ids.length} 篇`);
  }
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
      await Promise.all(ids.map((paperId) => addPaperToCollection(collection.id, paperId)));
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
    <LibraryHeader
      :paper-count="paperCount"
      :reading-count="readingCount"
      :is-uploading="isUploading"
      @export-bibtex="downloadBibtex"
      @open-import="isImportDialogOpen = true"
      @pick-files="pickFiles"
    />

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

    <LibraryToolbar
      v-model:query="filters.query"
      v-model:collection-id="filters.collectionId"
      v-model:tag="filters.tag"
      :filters="filters"
      :collections="collections"
      @change-status="selectStatus"
      @reload="loadLibrary"
      @create-collection="createNewCollection"
    />

    <LibraryBulkBar
      v-if="checkedIds.length"
      v-model:collection-id="bulkCollectionId"
      :count="checkedIds.length"
      :collections="collections"
      :busy="isBulkBusy"
      @mark-read="markCheckedRead"
      @remove="removeChecked"
      @add-to-collection="addCheckedToCollection"
      @clear="clearChecked"
    />

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
          <button type="button" class="paper-library__upload" @click="pickFiles">上传 PDF</button>
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
        @remove="removePaper"
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

.paper-library__file-input {
  display: none;
}

/* 空状态复用与 Header 一致的按钮样式 */
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

.paper-library__text-button:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
</style>
