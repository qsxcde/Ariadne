<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import StateBlock from "@/shared/components/StateBlock.vue";
import PaperInspector from "@/features/reader/components/PaperInspector.vue";
import PaperMetadataDialog from "@/features/reader/components/PaperMetadataDialog.vue";
import PaperReader from "@/features/reader/components/PaperReader.vue";
import PaperToolbar from "@/pages/paper/PaperToolbar.vue";
import { explainSelection, getPaper } from "@/api/papers";
import { usePapers } from "@/features/library/composables/usePapers";
import { useReadingClock } from "@/features/reader/composables/useReadingClock";
import UploadStatusCard from "@/shared/components/UploadStatusCard.vue";
import { shortcutLabel } from "@/shared/utils/platform";
import type { AnnotationSummary, PaperDetail, PaperDocumentSummary } from "@/api";
import type { SelectionAskMode, UploadStatus } from "@/shared/types";
import { toErrorMessage } from "@/shared/utils/error";
import { formatFileSize } from "@/shared/utils/format";
import { uploadStepFromStatus } from "@/shared/utils/upload";

const props = defineProps<{
  paperId: string;
}>();

const emit = defineEmits<{
  back: [];
  openLibrary: [];
}>();

const {
  currentPaper,
  isLoading,
  errorMessage,
  loadPaper,
  saveReadingState,
  addNote,
} = usePapers();

const NARROW_QUERY = "(max-width: 1200px)";
const INSPECTOR_STORAGE_KEY = "scipal.inspector.collapsed";
const PROGRESS_THROTTLE_MS = 1200;
const STATUS_FEEDBACK_MS = 1800;

const isNarrow = ref(window.matchMedia(NARROW_QUERY).matches);
const isInspectorCollapsed = ref(
  window.localStorage.getItem(INSPECTOR_STORAGE_KEY) === "1" || isNarrow.value,
);
const isMetadataDialogOpen = ref(false);
const statusSaving = ref(false);
const statusFeedback = ref("");
const viewMode = ref<"text" | "pdf">("text");
const outlineVisible = ref(true);

const readerRef = ref<InstanceType<typeof PaperReader> | null>(null);
let statusFeedbackTimer: number | null = null;
let progressTimer: number | null = null;
let pendingProgress: number | null = null;

const inspectorShortcutHint = computed(
  () => `显示或隐藏论文面板（${shortcutLabel("\\")}）`,
);
/** 同一篇论文可能重复上传，取最近一次解析的文档，而不是最早那条记录。 */
const documentItem = computed<PaperDocumentSummary | null>(() => {
  const documents = currentPaper.value?.documents ?? [];
  if (!documents.length) {
    return null;
  }
  return [...documents].sort(
    (left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  )[0];
});
const primarySessionId = computed(() => currentPaper.value?.primary_session_id ?? "");

/** 解析完成前不渲染阅读器，避免打开一份空正文。 */
const documentStep = computed(() => uploadStepFromStatus(documentItem.value?.status));
const isDocumentReady = computed(() => documentStep.value.canOpen);
const documentStatus = computed<UploadStatus | null>(() => {
  const document = documentItem.value;
  if (!document) {
    return null;
  }
  const step = documentStep.value;
  return {
    fileName: document.filename,
    fileSizeLabel: formatFileSize(document.file_size),
    phase: step.phase,
    progress: step.progress,
    stageLabel: step.stageLabel,
    canOpen: step.canOpen,
    errorMessage: document.status === "failed" ? "解析失败，请重新上传" : undefined,
  };
});
const isParseFailed = computed(() => documentItem.value?.status === "failed");
const pendingTitle = computed(() =>
  isParseFailed.value ? "这篇论文解析失败" : `${documentStep.value.stageLabel} · ${documentStep.value.progress}%`,
);
const pendingDescription = computed(() =>
  isParseFailed.value
    ? "可以回到文献库重新上传，或稍后点「刷新」重试。"
    : "解析完成后会自动打开阅读器，也可以稍后点「刷新」。",
);

const POLL_INTERVAL_MS = 2000;
let pollTimer: number | null = null;

function stopDocumentPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

/** 轮询走静默刷新，避免每 2 秒触发 isLoading 让工具栏闪动。 */
async function pollDocument(): Promise<void> {
  try {
    currentPaper.value = await getPaper(props.paperId);
  } catch {
    // 单次失败忽略，下一轮继续
  }
}

function startDocumentPolling(): void {
  if (pollTimer !== null) {
    return;
  }
  pollTimer = window.setInterval(() => {
    if (isDocumentReady.value || isParseFailed.value) {
      stopDocumentPolling();
      return;
    }
    void pollDocument();
  }, POLL_INTERVAL_MS);
}

watch(
  () => [isDocumentReady.value, documentItem.value?.id, isParseFailed.value] as const,
  ([ready, , failed]) => {
    if (ready || failed) {
      stopDocumentPolling();
      return;
    }
    startDocumentPolling();
  },
  { immediate: true },
);

useReadingClock(toRef(props, "paperId"));

function toggleInspector(): void {
  isInspectorCollapsed.value = !isInspectorCollapsed.value;
  window.localStorage.setItem(
    INSPECTOR_STORAGE_KEY,
    isInspectorCollapsed.value ? "1" : "0",
  );
}

function handleInspectorShortcut(event: KeyboardEvent): void {
  if ((event.metaKey || event.ctrlKey) && event.key === "\\") {
    event.preventDefault();
    toggleInspector();
    return;
  }
  if (
    event.key === "Escape" &&
    isNarrow.value &&
    !isInspectorCollapsed.value &&
    !window.document.querySelector(".palette, .el-overlay")
  ) {
    event.preventDefault();
    toggleInspector();
  }
}

/** 窄屏把 Inspector 变成抽屉：进入窄屏自动收起，回到宽屏恢复手动偏好。 */
function syncViewport(): void {
  const narrow = window.matchMedia(NARROW_QUERY).matches;
  if (narrow && !isNarrow.value) {
    isInspectorCollapsed.value = true;
  } else if (!narrow && isNarrow.value) {
    isInspectorCollapsed.value =
      window.localStorage.getItem(INSPECTOR_STORAGE_KEY) === "1";
  }
  isNarrow.value = narrow;
}

async function refresh(): Promise<void> {
  await loadPaper(props.paperId);
}

async function handleMetadataSaved(): Promise<void> {
  await loadPaper(props.paperId);
}

function jumpToSection(title: string): void {
  readerRef.value?.revealSection(title);
}

function locateAnnotation(annotation: AnnotationSummary): void {
  readerRef.value?.jumpToLocation(
    annotation.chunk_id ?? undefined,
    annotation.page_start ?? undefined,
  );
}

async function changeStatus(status: string): Promise<void> {
  if (!currentPaper.value) return;
  currentPaper.value.reading_status = status as PaperDetail["reading_status"];
  statusSaving.value = true;
  const saved = await saveReadingState(props.paperId, {
    reading_status: currentPaper.value.reading_status,
  });
  statusSaving.value = false;
  if (!saved) return;
  statusFeedback.value = "已保存";
  if (statusFeedbackTimer !== null) {
    window.clearTimeout(statusFeedbackTimer);
  }
  statusFeedbackTimer = window.setTimeout(() => {
    statusFeedback.value = "";
    statusFeedbackTimer = null;
  }, STATUS_FEEDBACK_MS);
}

function handleProgress(ratio: number): void {
  pendingProgress = ratio;
  if (progressTimer !== null) {
    return;
  }
  progressTimer = window.setTimeout(async () => {
    progressTimer = null;
    const next = pendingProgress;
    pendingProgress = null;
    if (next === null || !documentItem.value) return;
    await saveReadingState(props.paperId, {
      progress: next,
      last_location: {
        document_id: documentItem.value.id,
        scroll_ratio: next,
      },
    });
  }, PROGRESS_THROTTLE_MS);
}

async function handleAsk(text: string, mode: SelectionAskMode): Promise<void> {
  if (mode === "followup") {
    await quickNote(text);
    return;
  }
  try {
    const result = await explainSelection(props.paperId, text, mode);
    const title = mode === "translate" ? "翻译" : mode === "simplify" ? "简化" : "解释";
    await ElMessageBox.alert(result.explanation, title, {
      confirmButtonText: "知道了",
    });
  } catch (error) {
    ElMessage.error(toErrorMessage(error, "解释失败"));
  }
}

async function quickNote(text: string): Promise<void> {
  const trimmed = text.trim();
  if (!trimmed) return;
  const annotation = await addNote(props.paperId, "", trimmed);
  if (annotation) {
    ElMessage.success("已保存到笔记");
  }
}

onMounted(async () => {
  await refresh();
  window.addEventListener("keydown", handleInspectorShortcut);
  window.addEventListener("resize", syncViewport);
});

watch(
  () => props.paperId,
  async () => {
    await refresh();
  },
);

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleInspectorShortcut);
  window.removeEventListener("resize", syncViewport);
  if (statusFeedbackTimer !== null) {
    window.clearTimeout(statusFeedbackTimer);
  }
  if (progressTimer !== null) {
    window.clearTimeout(progressTimer);
  }
  stopDocumentPolling();
});
</script>

<template>
  <section class="paper-workspace" aria-label="论文阅读工作台">
    <PaperToolbar
      :paper="currentPaper"
      :is-loading="isLoading"
      :status-saving="statusSaving"
      :status-feedback="statusFeedback"
      :inspector-collapsed="isInspectorCollapsed"
      :shortcut-hint="inspectorShortcutHint"
      :view-mode="viewMode"
      :outline-visible="outlineVisible"
      @back="emit('back')"
      @toggle-inspector="toggleInspector"
      @edit-metadata="isMetadataDialogOpen = true"
      @refresh="refresh"
      @change-status="changeStatus"
      @set-view-mode="viewMode = $event"
      @toggle-outline="outlineVisible = !outlineVisible"
    />

    <PaperMetadataDialog
      :visible="isMetadataDialogOpen"
      :paper="currentPaper"
      @close="isMetadataDialogOpen = false"
      @saved="handleMetadataSaved"
    />

    <StateBlock
      v-if="errorMessage"
      kind="error"
      compact
      :description="errorMessage"
      action-label="重试"
      @action="refresh"
    />

    <div
      v-if="currentPaper && documentItem && primarySessionId && isDocumentReady"
      class="paper-workspace__body"
      :class="{ 'paper-workspace__body--collapsed': isInspectorCollapsed }"
    >
      <PaperReader
        ref="readerRef"
        :session-id="primarySessionId"
        :document-id="documentItem.id"
        :initial-progress="currentPaper.progress"
        :show-close="false"
        :chrome="false"
        :view-mode="viewMode"
        :outline-visible="outlineVisible"
        @update:view-mode="viewMode = $event"
        @update:outline-visible="outlineVisible = $event"
        @note="quickNote"
        @ask="handleAsk"
        @progress="handleProgress"
        @close="emit('back')"
      />

      <button
        v-show="!isInspectorCollapsed"
        type="button"
        class="paper-workspace__scrim"
        aria-label="关闭论文面板"
        @click="toggleInspector"
      />
      <aside
        v-show="!isInspectorCollapsed"
        class="paper-workspace__inspector"
        aria-label="论文检查器"
      >
        <PaperInspector
          :paper-id="paperId"
          :session-id="primarySessionId"
          @jump-section="jumpToSection"
          @locate="locateAnnotation"
        />
      </aside>
    </div>

    <div v-else-if="currentPaper && documentStatus" class="paper-workspace__pending">
      <UploadStatusCard :status="documentStatus" />
      <StateBlock
        :kind="isParseFailed ? 'error' : 'loading'"
        :title="pendingTitle"
        :description="pendingDescription"
        :action-label="isParseFailed ? '回到文献库' : '刷新'"
        @action="isParseFailed ? emit('openLibrary') : refresh"
      />
    </div>

    <StateBlock
      v-else-if="currentPaper"
      kind="loading"
      title="正文还在解析或索引中"
      description="稍后点击「刷新」；解析完成后即可在这里阅读、记笔记。"
      action-label="回到文献库"
      @action="emit('openLibrary')"
    />
  </section>
</template>

<style scoped>
.paper-workspace {
  display: flex;
  min-width: 0;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-bg);
}

.paper-workspace__pending {
  display: flex;
  width: 100%;
  max-width: 720px;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  margin: 0 auto;
  padding: 48px 24px;
  overflow-y: auto;
}

.paper-workspace__pending :deep(.state-block) {
  width: 100%;
}

.paper-workspace__body {
  display: grid;
  width: 100%;
  max-width: 1680px;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) 340px;
  grid-template-rows: minmax(0, 1fr);
  margin: 0 auto;
  overflow: hidden;
}

.paper-workspace__body--collapsed {
  grid-template-columns: minmax(0, 1fr);
}

.paper-workspace__inspector {
  display: flex;
  min-height: 0;
  height: 100%;
  flex-direction: column;
  overflow: hidden;
  border-left: 1px solid var(--color-border);
  background: var(--color-panel);
}

.paper-workspace__scrim {
  display: none;
}

@media (max-width: 1200px) {
  .paper-workspace__body {
    position: relative;
    grid-template-columns: minmax(0, 1fr);
  }

  .paper-workspace__scrim {
    position: absolute;
    inset: 0;
    z-index: var(--z-page-scrim);
    display: block;
    border: 0;
    background: var(--overlay-page);
  }

  .paper-workspace__inspector {
    position: absolute;
    inset: 0 0 0 auto;
    z-index: var(--z-page-panel);
    width: min(360px, 88vw);
    box-shadow: var(--shadow-drawer);
  }
}
</style>
