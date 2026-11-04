<script setup lang="ts">
import { defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import PaperOutline from "@/features/reader/components/PaperOutline.vue";
import PaperReaderBar from "@/features/reader/components/PaperReaderBar.vue";
import PaperSelectionMenu from "@/features/reader/components/PaperSelectionMenu.vue";
import PaperTextView from "@/features/reader/components/PaperTextView.vue";
import { usePaperReader } from "@/features/reader/composables/usePaperReader";
import type { SelectionAskMode } from "@/shared/types";

// pdf.js 体积较大，只在切到「原页」时才加载
const PdfViewer = defineAsyncComponent(() => import("@/features/reader/components/PdfViewer.vue"));

const props = defineProps<{
  sessionId: string;
  documentId: string;
  initialProgress?: number;
  showClose?: boolean;
}>();

const emit = defineEmits<{
  ask: [text: string, mode: SelectionAskMode];
  note: [text: string];
  progress: [ratio: number];
  close: [];
}>();

const {
  content,
  outline,
  isLoading,
  errorMessage,
  activeBlockId,
  activeSectionKey,
  citationBoxes,
  citationPage,
  load,
  revealBlock,
  mount,
  unmount,
} = usePaperReader();

const textViewRef = ref<InstanceType<typeof PaperTextView> | null>(null);
const outlineVisible = ref(true);
const viewMode = ref<"text" | "pdf">("text");
const pdfPage = ref(1);
const progressRatio = ref(props.initialProgress ?? 0);
const selectionMenu = ref<{ text: string; x: number; y: number } | null>(null);

function handleProgress(ratio: number): void {
  progressRatio.value = ratio;
  emit("progress", ratio);
}

// 引用命中时自动切到原页并定位
watch([citationPage, citationBoxes], () => {
  const page = citationPage.value ?? citationBoxes.value[0]?.page_number ?? null;
  if (!page) {
    return;
  }
  pdfPage.value = page;
  viewMode.value = "pdf";
});

function handleOutlineSelect(blockId: string): void {
  if (!blockId) {
    return;
  }
  textViewRef.value?.scrollToBlock(blockId);
  revealBlock([blockId]);
}

function revealSection(title: string): void {
  textViewRef.value?.revealSection(title);
}

/** 笔记跳转：优先匹配正文块 id，其次按页码落到最近的块。 */
function jumpToLocation(chunkId?: string | null, page?: number | null): void {
  viewMode.value = "text";
  void nextTick(() => textViewRef.value?.jumpToLocation(chunkId, page));
}

defineExpose({ revealSection, jumpToLocation });

function noteSelection(): void {
  const menu = selectionMenu.value;
  if (!menu) {
    return;
  }
  emit("note", menu.text);
  selectionMenu.value = null;
  window.getSelection()?.removeAllRanges();
}

function askSelection(mode: SelectionAskMode): void {
  const menu = selectionMenu.value;
  if (!menu) {
    return;
  }
  emit("ask", menu.text, mode);
  selectionMenu.value = null;
  window.getSelection()?.removeAllRanges();
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    selectionMenu.value = null;
  }
}

async function restoreReaderPosition(): Promise<void> {
  await nextTick();
  textViewRef.value?.scrollToActive();
  textViewRef.value?.restore();
  textViewRef.value?.syncActiveSection();
}

watch([activeBlockId, content], async () => {
  if (!activeBlockId.value) {
    return;
  }
  await nextTick();
  textViewRef.value?.scrollToActive();
});

watch(
  () => props.documentId,
  async (id) => {
    await load(props.sessionId, id);
    await restoreReaderPosition();
  },
);

onMounted(async () => {
  mount();
  await load(props.sessionId, props.documentId);
  await restoreReaderPosition();
  window.document.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  unmount();
  window.document.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <section class="paper-reader" aria-label="论文原文">
    <PaperReaderBar
      :content="content"
      :view-mode="viewMode"
      :outline-visible="outlineVisible"
      :show-close="showClose !== false"
      @set-view-mode="viewMode = $event"
      @toggle-outline="outlineVisible = !outlineVisible"
      @close="emit('close')"
    />

    <div class="paper-reader__main">
      <div v-if="viewMode === 'text'" class="paper-reader__spine" aria-hidden="true">
        <span
          class="paper-reader__spine-fill"
          :style="{ height: `${Math.round(progressRatio * 100)}%` }"
        >
          <span class="paper-reader__spine-marker" />
        </span>
      </div>

      <PaperOutline
        v-if="viewMode === 'text' && outlineVisible && outline.length"
        :items="outline"
        :active-key="activeSectionKey"
        @select="handleOutlineSelect"
      />

      <PdfViewer
        v-if="viewMode === 'pdf'"
        :boxes="citationBoxes"
        :document-id="props.documentId"
        :page="pdfPage"
        :session-id="props.sessionId"
        @update:page="pdfPage = $event"
      />

      <PaperTextView
        v-else
        ref="textViewRef"
        :content="content"
        :is-loading="isLoading"
        :error-message="errorMessage"
        :active-block-id="activeBlockId"
        :initial-progress="initialProgress"
        @progress="handleProgress"
        @ask="(text, mode) => emit('ask', text, mode)"
        @select="(text, x, y) => (selectionMenu = { text, x, y })"
        @clear-selection="selectionMenu = null"
      />
    </div>

    <PaperSelectionMenu
      v-if="selectionMenu"
      :menu="selectionMenu"
      @note="noteSelection"
      @ask="askSelection"
    />
  </section>
</template>

<style scoped>
.paper-reader {
  display: flex;
  min-width: 0;
  flex-direction: column;
  background: var(--color-panel);
  border-right: 1px solid var(--color-border);
}

.paper-reader__main {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
}

/* 阅读脊线：沿正文右缘显示进度，是阅读页唯一常驻的朱砂标记。 */
.paper-reader__spine {
  position: absolute;
  top: 24px;
  right: 10px;
  bottom: 24px;
  z-index: 2;
  width: 1px;
  background: var(--color-border);
  pointer-events: none;
}

.paper-reader__spine-fill {
  position: absolute;
  top: 0;
  left: 0;
  width: 1px;
  background: var(--color-accent);
  transition: height 160ms linear;
}

.paper-reader__spine-marker {
  position: absolute;
  bottom: -2px;
  left: -2px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-accent);
}

@media (max-width: 1200px) {
  .paper-reader__spine {
    top: 16px;
    right: 7px;
    bottom: 16px;
  }
}
</style>
