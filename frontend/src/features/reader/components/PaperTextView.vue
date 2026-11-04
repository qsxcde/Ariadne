<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import MarkdownContent from "@/shared/components/MarkdownContent.vue";
import { usePaperReader } from "@/features/reader/composables/usePaperReader";
import { findBlockBySection } from "@/shared/utils/section";
import type { PaperBlock, PaperContent } from "@/api";
import type { SelectionAskMode } from "@/shared/types";

const props = defineProps<{
  content: PaperContent | null;
  isLoading: boolean;
  errorMessage: string;
  activeBlockId: string | null;
  initialProgress?: number;
}>();

const emit = defineEmits<{
  progress: [ratio: number];
  ask: [text: string, mode: SelectionAskMode];
  select: [text: string, x: number, y: number];
  clearSelection: [];
}>();

const { revealBlock, setActiveSection } = usePaperReader();

const scrollRef = ref<HTMLElement | null>(null);
const bodyRef = ref<HTMLElement | null>(null);
const progressRatio = ref(props.initialProgress ?? 0);

type ReaderNode =
  | { kind: "section"; key: string; title: string; level: number }
  | { kind: "block"; key: string; block: PaperBlock };

/** 章节标题由 section_path 变化推导，避免正文里重复输出标题。 */
const nodes = computed<ReaderNode[]>(() => {
  const blocks = props.content?.blocks ?? [];
  const result: ReaderNode[] = [];
  let lastPath = "";

  blocks.forEach((block, index) => {
    const path = block.section_path.join(" > ");
    if (path && path !== lastPath) {
      lastPath = path;
      result.push({
        kind: "section",
        key: `section-${path}`,
        title: block.section_path[block.section_path.length - 1] ?? path,
        level: Math.min(block.section_path.length + 1, 4),
      });
    }
    result.push({ kind: "block", key: block.id || `block-${index}`, block });
  });

  return result;
});

let scrollFrame = 0;

/** 滚动时用「最后一个越过顶部阈值的小节标题」标记当前章节。 */
function syncActiveSection(): void {
  const container = scrollRef.value;
  if (!container) {
    return;
  }
  const threshold = container.getBoundingClientRect().top + 64;
  const headings = container.querySelectorAll<HTMLElement>("[data-section-key]");
  let current: string | null = null;
  headings.forEach((heading) => {
    if (heading.getBoundingClientRect().top <= threshold) {
      current = heading.dataset.sectionKey ?? null;
    }
  });
  setActiveSection(current);
}

function handleScroll(): void {
  emit("clearSelection");
  if (scrollFrame) {
    return;
  }
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0;
    syncActiveSection();
    const container = scrollRef.value;
    if (!container) {
      return;
    }
    const max = container.scrollHeight - container.clientHeight;
    const ratio = max > 0 ? container.scrollTop / max : 0;
    progressRatio.value = ratio;
    emit("progress", ratio);
  });
}

function restore(): void {
  const container = scrollRef.value;
  const ratio = props.initialProgress ?? 0;
  if (!container || ratio <= 0) {
    return;
  }
  const max = container.scrollHeight - container.clientHeight;
  container.scrollTop = Math.max(0, Math.min(1, ratio)) * max;
  progressRatio.value = Math.max(0, Math.min(1, ratio));
}

function scrollToBlock(blockId: string): void {
  const element = window.document.getElementById(`paper-block-${blockId}`);
  element?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToActive(): void {
  const id = props.activeBlockId;
  if (id) {
    scrollToBlock(id);
  }
}

/** 按章节标题定位：优先末级路径完全匹配，退化为路径包含。 */
function revealSection(title: string): void {
  const block = findBlockBySection(props.content?.blocks ?? [], title);
  if (block) {
    revealBlock([block.id]);
  }
}

/** 笔记跳转：优先匹配正文块 id，其次按页码落到最近的块。 */
function jumpToLocation(chunkId?: string | null, page?: number | null): void {
  void nextTick(() => {
    if (chunkId && window.document.getElementById(`paper-block-${chunkId}`)) {
      scrollToBlock(chunkId);
      revealBlock([chunkId]);
      return;
    }
    const blocks = props.content?.blocks ?? [];
    const block =
      (page ? blocks.find((item) => item.page_number >= page) : undefined) ?? blocks[0];
    if (block) {
      scrollToBlock(block.id);
      revealBlock([block.id]);
    }
  });
}

/** 选区浮条：只处理落在正文区域内的选区。 */
function handleMouseUp(): void {
  const selection = window.getSelection();
  const text = selection?.toString().trim() ?? "";
  const container = bodyRef.value;
  if (!selection || !text || text.length < 4 || !container || selection.rangeCount === 0) {
    emit("clearSelection");
    return;
  }
  const range = selection.getRangeAt(0);
  if (!container.contains(range.commonAncestorContainer)) {
    emit("clearSelection");
    return;
  }
  const rect = range.getBoundingClientRect();
  emit("select", text, rect.left + rect.width / 2, rect.top);
}

onMounted(() => {
  window.document.addEventListener("mouseup", handleMouseUp);
});

onBeforeUnmount(() => {
  window.document.removeEventListener("mouseup", handleMouseUp);
});

defineExpose({
  restore,
  scrollToActive,
  scrollToBlock,
  syncActiveSection,
  revealSection,
  jumpToLocation,
});
</script>

<template>
  <div ref="scrollRef" class="paper-reader__scroll" @scroll="handleScroll">
    <p v-if="isLoading" class="paper-reader__state">正在读取解析结果…</p>
    <p v-else-if="errorMessage" class="paper-reader__state paper-reader__state--error">
      {{ errorMessage }}
    </p>
    <p v-else-if="!nodes.length" class="paper-reader__state">
      该论文还没有可展示的结构化正文，请等待解析完成或重新上传。
    </p>

    <article v-else ref="bodyRef" class="paper-reader__body">
      <template v-for="node in nodes" :key="node.key">
        <h2
          v-if="node.kind === 'section'"
          class="paper-reader__section"
          :class="`paper-reader__section--h${node.level}`"
          :data-section-key="node.key"
        >
          {{ node.title }}
        </h2>
        <div
          v-else
          :id="node.block.id ? `paper-block-${node.block.id}` : undefined"
          class="paper-reader__block"
          :class="{
            'is-active': activeBlockId === node.block.id,
            'paper-reader__block--table': node.block.type === 'table',
            'paper-reader__block--formula': node.block.type === 'formula',
          }"
        >
          <p v-if="node.block.page_number" class="paper-reader__anchor" aria-hidden="true">
            p.{{ node.block.page_number }}
          </p>
          <button
            v-if="node.block.type === 'table' || node.block.type === 'formula'"
            type="button"
            class="paper-reader__block-action"
            @click.stop="emit('ask', node.block.text, 'explain')"
          >
            {{ node.block.type === "table" ? "解释表格" : "解释公式" }}
          </button>
          <p v-if="node.block.type === 'title'" class="paper-reader__title">
            {{ node.block.text }}
          </p>
          <pre v-else-if="node.block.type === 'table'" class="paper-reader__pre">{{
            node.block.text
          }}</pre>
          <p v-else-if="node.block.type === 'formula'" class="paper-reader__formula">
            {{ node.block.text }}
          </p>
          <MarkdownContent v-else :text="node.block.text" />
        </div>
      </template>
    </article>
  </div>
</template>

<style scoped>
.paper-reader__scroll {
  flex: 1;
  min-width: 0;
  padding: 26px 30px 96px;
  overflow-y: auto;
}

.paper-reader__body {
  max-width: var(--reading-max);
  margin: 0 auto;
}

.paper-reader__state {
  max-width: 520px;
  margin: 40px auto;
  color: var(--color-text-muted);
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
}

.paper-reader__state--error {
  color: var(--color-danger);
}

.paper-reader__section {
  margin: 34px 0 12px;
  color: var(--color-text);
  font-family: var(--font-serif);
  line-height: 1.3;
  letter-spacing: -0.01em;
  scroll-margin-top: 24px;
}

.paper-reader__section--h2 {
  font-size: 21px;
}

.paper-reader__section--h3 {
  font-size: 17px;
}

.paper-reader__section--h4 {
  font-size: 15px;
  color: var(--color-text-soft);
}

.paper-reader__block {
  position: relative;
  margin: 0 -12px;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  scroll-margin-top: 96px;
  transition:
    background 0.24s ease,
    box-shadow 0.24s ease;
}

.paper-reader__block + .paper-reader__block {
  margin-top: 4px;
}

.paper-reader__block-action {
  position: absolute;
  top: 8px;
  right: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: var(--color-surface);
  padding: 2px 6px;
  color: var(--color-accent);
  cursor: pointer;
  font-size: 11px;
}

.paper-reader__block.is-active {
  background: var(--color-accent-soft);
  box-shadow: -3px 0 0 var(--color-accent);
}

.paper-reader__anchor {
  position: absolute;
  top: 6px;
  left: -46px;
  width: 34px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-align: right;
}

.paper-reader__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: 700;
  line-height: 1.35;
}

.paper-reader__formula {
  margin: 0;
  color: var(--color-text-body);
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.7;
  word-break: break-word;
}

.paper-reader__pre {
  margin: 0;
  padding: 10px 12px;
  overflow-x: auto;
  color: var(--color-text-body);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  background: var(--color-surface-alt);
  border-radius: var(--radius-sm);
}

.paper-reader__block :deep(.markdown-content) {
  color: var(--color-text-body);
  font-family: var(--font-serif);
  font-size: 16px;
  line-height: 1.9;
}

.paper-reader__block :deep(.markdown-content p + p) {
  margin-top: 10px;
}

.paper-reader__block :deep(.markdown-content ul),
.paper-reader__block :deep(.markdown-content ol) {
  display: grid;
  gap: 6px;
  margin: 10px 0 0;
  padding-left: 22px;
}

@media (max-width: 1200px) {
  .paper-reader__scroll {
    padding: 22px 22px 80px;
  }

  .paper-reader__anchor {
    display: none;
  }
}
</style>
