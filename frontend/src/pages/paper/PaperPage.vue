<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, toRef, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import StateBlock from "@/shared/components/StateBlock.vue";
import PaperInspector from "@/features/reader/components/PaperInspector.vue";
import PaperMetadataDialog from "@/features/reader/components/PaperMetadataDialog.vue";
import PaperReader from "@/features/reader/components/PaperReader.vue";
import PaperWorkspaceBar from "@/pages/paper/PaperToolbar.vue";
import { explainSelection } from "@/api/papers";
import { usePapers } from "@/features/library/composables/usePapers";
import { useReadingClock } from "@/features/reader/composables/useReadingClock";
import { shortcutLabel } from "@/shared/utils/platform";
import type { AnnotationSummary, PaperDetail, PaperDocumentSummary } from "@/api";
import type { SelectionAskMode } from "@/shared/types";
import { toErrorMessage } from "@/shared/utils/error";

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

const readerRef = ref<InstanceType<typeof PaperReader> | null>(null);
let statusFeedbackTimer: number | null = null;
let progressTimer: number | null = null;
let pendingProgress: number | null = null;

const inspectorShortcutHint = computed(
  () => `显示或隐藏论文面板（${shortcutLabel("\\")}）`,
);
const documentItem = computed<PaperDocumentSummary | null>(
  () => (currentPaper.value?.documents ?? [])[0] ?? null,
);
const primarySessionId = computed(() => currentPaper.value?.primary_session_id ?? "");

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
});
</script>

<template>
  <section class="paper-workspace" aria-label="论文阅读工作台">
    <PaperWorkspaceBar
      :paper="currentPaper"
      :is-loading="isLoading"
      :status-saving="statusSaving"
      :status-feedback="statusFeedback"
      :inspector-collapsed="isInspectorCollapsed"
      :shortcut-hint="inspectorShortcutHint"
      @back="emit('back')"
      @toggle-inspector="toggleInspector"
      @edit-metadata="isMetadataDialogOpen = true"
      @refresh="refresh"
      @change-status="changeStatus"
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
      v-if="currentPaper && documentItem && primarySessionId"
      class="paper-workspace__body"
      :class="{ 'paper-workspace__body--collapsed': isInspectorCollapsed }"
    >
      <PaperReader
        ref="readerRef"
        :session-id="primarySessionId"
        :document-id="documentItem.id"
        :initial-progress="currentPaper.progress"
        :show-close="false"
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
