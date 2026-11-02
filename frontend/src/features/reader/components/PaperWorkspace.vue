<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Refresh } from "@element-plus/icons-vue";
import PaperReader from "./PaperReader.vue";
import { usePapers } from "../../../composables/usePapers";
import { explainSelection } from "../../../api/papers";
import type { AnnotationSummary, PaperDocumentSummary } from "../../../api";
import type { SelectionAskMode } from "../../../types";

const props = defineProps<{
  paperId: string;
}>();

const emit = defineEmits<{
  back: [];
  openLibrary: [];
}>();

const {
  currentPaper,
  brief,
  isLoading,
  isBriefLoading,
  errorMessage,
  loadPaper,
  loadBrief,
  saveReadingState,
  addNote,
  removeAnnotation,
} = usePapers();

const noteDraft = ref("");
const statusSaving = ref(false);
let progressTimer: number | null = null;
let pendingProgress: number | null = null;

const documentItem = computed<PaperDocumentSummary | null>(
  () => (currentPaper.value?.documents ?? [])[0] ?? null,
);
const primarySessionId = computed(() => currentPaper.value?.primary_session_id ?? "");
const annotations = computed<AnnotationSummary[]>(() => currentPaper.value?.annotations ?? []);
const currentBrief = computed(() =>
  brief.value?.paper_id === props.paperId ? brief.value : null,
);

const STATUS_OPTIONS = [
  { value: "inbox", label: "待读" },
  { value: "queued", label: "队列中" },
  { value: "skimming", label: "速读" },
  { value: "reading", label: "在读" },
  { value: "read", label: "已读" },
  { value: "archived", label: "已归档" },
];

const STATUS_LABELS: Record<string, string> = Object.fromEntries(
  STATUS_OPTIONS.map((option) => [option.value, option.label]),
);

function progressPercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function annotationLabel(annotation: AnnotationSummary): string {
  if (annotation.type === "highlight") return "高亮";
  if (annotation.type === "question") return "问题";
  return "笔记";
}

async function refresh(): Promise<void> {
  await loadPaper(props.paperId);
}

async function generateBrief(): Promise<void> {
  await loadBrief(props.paperId);
  if (brief.value) {
    ElMessage.success("速读卡已生成");
  }
}

async function changeStatus(): Promise<void> {
  if (!currentPaper.value) return;
  statusSaving.value = true;
  try {
    await saveReadingState(props.paperId, {
      reading_status: currentPaper.value.reading_status,
    });
  } finally {
    statusSaving.value = false;
  }
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
  }, 1200);
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
    ElMessage.error(error instanceof Error ? error.message : "解释失败");
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

async function saveNote(): Promise<void> {
  const content = noteDraft.value.trim();
  if (!content) return;
  const annotation = await addNote(props.paperId, content);
  if (annotation) {
    noteDraft.value = "";
    ElMessage.success("已保存笔记");
  }
}

async function deleteNote(annotation: AnnotationSummary): Promise<void> {
  try {
    await ElMessageBox.confirm("删除这条笔记？", "删除笔记", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  await removeAnnotation(annotation.id);
}

onMounted(async () => {
  await refresh();
});

watch(
  () => props.paperId,
  async () => {
    await refresh();
  },
);

onBeforeUnmount(() => {
  if (progressTimer !== null) {
    window.clearTimeout(progressTimer);
  }
});
</script>

<template>
  <section class="paper-workspace" aria-label="论文阅读工作台">
    <header class="paper-workspace__bar">
      <button type="button" class="paper-workspace__back" @click="emit('back')">
        <ArrowLeft class="paper-workspace__icon" /> 返回
      </button>
      <div class="paper-workspace__meta">
        <p class="paper-workspace__eyebrow">阅读工作台</p>
        <h1 class="paper-workspace__title">{{ currentPaper?.title || "正在载入论文…" }}</h1>
        <p class="paper-workspace__sub">
          <span v-if="(currentPaper?.authors ?? []).length">{{ (currentPaper?.authors ?? []).join("、") }}</span>
          <span v-if="currentPaper?.year"> · {{ currentPaper.year }}</span>
          <span v-if="currentPaper?.venue"> · {{ currentPaper.venue }}</span>
          <span v-if="documentItem"> · 解析 {{ documentItem.status }}<template v-if="documentItem.parse_quality_status">（{{ documentItem.parse_quality_status }}）</template></span>
        </p>
      </div>
      <div class="paper-workspace__actions">
        <select
          v-if="currentPaper"
          v-model="currentPaper.reading_status"
          class="paper-workspace__status"
          :disabled="statusSaving"
          @change="changeStatus"
        >
          <option v-for="option in STATUS_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <button type="button" class="paper-workspace__refresh" :disabled="isLoading" @click="refresh">
          <Refresh class="paper-workspace__icon" /> 刷新
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="paper-workspace__error">{{ errorMessage }}</p>

    <div v-if="currentPaper" class="paper-workspace__progress">
      <span>{{ STATUS_LABELS[currentPaper.reading_status] || currentPaper.reading_status }}</span>
      <span class="paper-workspace__progress-track" aria-hidden="true">
        <span
          class="paper-workspace__progress-fill"
          :style="{ width: `${progressPercent(currentPaper.progress)}%` }"
        />
      </span>
      <span>{{ progressPercent(currentPaper.progress) }}%</span>
    </div>

    <div v-if="currentPaper && documentItem && primarySessionId" class="paper-workspace__body">
      <PaperReader
        :session-id="primarySessionId"
        :document-id="documentItem.id"
        :initial-progress="currentPaper.progress"
        @note="quickNote"
        @ask="handleAsk"
        @progress="handleProgress"
        @close="emit('back')"
      />

      <aside class="paper-workspace__notes" aria-label="笔记">
        <header class="paper-workspace__notes-header">
          <div>
            <p class="paper-workspace__eyebrow">速读卡 · 笔记</p>
            <h2 class="paper-workspace__notes-title">{{ annotations.length }} 条笔记</h2>
          </div>
        </header>

        <section class="paper-workspace__brief">
          <header class="paper-workspace__brief-head">
            <span class="paper-workspace__eyebrow">5 分钟速读</span>
            <button
              type="button"
              class="paper-workspace__secondary"
              :disabled="isBriefLoading"
              @click="generateBrief"
            >
              {{ isBriefLoading ? "生成中…" : currentBrief ? "重新生成" : "生成速读卡" }}
            </button>
          </header>
          <p v-if="!currentBrief" class="paper-workspace__empty">
            基于章节摘要生成 TL;DR、贡献、方法、实验与局限，每条结论带原文引用。
          </p>
          <div v-else class="paper-workspace__brief-body">
            <p class="paper-workspace__tldr">{{ currentBrief.tldr }}</p>
            <div v-if="(currentBrief.contributions ?? []).length">
              <h3>贡献</h3>
              <ul class="paper-workspace__brief-list">
                <li v-for="item in currentBrief.contributions ?? []" :key="item">{{ item }}</li>
              </ul>
            </div>
            <p><strong>方法：</strong>{{ currentBrief.method }}</p>
            <p><strong>实验：</strong>{{ currentBrief.experiments }}</p>
            <p><strong>局限：</strong>{{ currentBrief.limitations }}</p>
            <div v-if="(currentBrief.takeaways ?? []).length">
              <h3>阅读要点</h3>
              <ul class="paper-workspace__brief-list">
                <li v-for="item in currentBrief.takeaways ?? []" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </section>

        <div class="paper-workspace__note-compose">
          <textarea
            v-model="noteDraft"
            class="paper-workspace__textarea"
            rows="3"
            placeholder="写一条笔记…"
          />
          <button type="button" class="paper-workspace__primary" @click="saveNote">保存笔记</button>
        </div>

        <div class="paper-workspace__note-list">
          <p v-if="!annotations.length" class="paper-workspace__empty">还没有笔记。选中正文可快速记笔记。</p>
          <article v-for="annotation in annotations" :key="annotation.id" class="paper-note">
            <header class="paper-note__head">
              <span class="paper-note__type">{{ annotationLabel(annotation) }}</span>
              <button type="button" class="paper-note__delete" @click="deleteNote(annotation)">删除</button>
            </header>
            <blockquote v-if="annotation.quote" class="paper-note__quote">{{ annotation.quote }}</blockquote>
            <p v-if="annotation.content" class="paper-note__content">{{ annotation.content }}</p>
          </article>
        </div>
      </aside>
    </div>

    <div v-else-if="currentPaper" class="paper-workspace__waiting">
      <p>论文已入库，正文还在解析或索引中。</p>
      <p>稍后点击「刷新」；解析完成后即可在这里阅读、记笔记。</p>
      <button type="button" class="paper-workspace__primary" @click="emit('openLibrary')">
        回到文献库
      </button>
    </div>
  </section>
</template>

<style scoped>
.paper-workspace {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  background: var(--color-bg);
}

.paper-workspace__bar {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 26px 14px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-panel);
}

.paper-workspace__back,
.paper-workspace__refresh,
.paper-workspace__primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 12px;
  padding: 7px 10px;
}

.paper-workspace__primary {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: #fff;
}

.paper-workspace__back:hover,
.paper-workspace__refresh:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.paper-workspace__icon {
  width: 14px;
  height: 14px;
}

.paper-workspace__meta {
  min-width: 0;
  flex: 1;
}

.paper-workspace__eyebrow {
  margin: 0 0 4px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.paper-workspace__title {
  margin: 0;
  overflow: hidden;
  font-size: 18px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-workspace__sub {
  margin: 5px 0 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.paper-workspace__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.paper-workspace__status {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 12px;
  padding: 7px 9px;
}

.paper-workspace__progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 26px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-workspace__progress-track {
  height: 4px;
  flex: 1;
  overflow: hidden;
  border-radius: 999px;
  background: var(--color-border);
}

.paper-workspace__progress-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--color-accent);
}

.paper-workspace__body {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(0, 1fr) 300px;
}

.paper-workspace__notes {
  display: flex;
  min-height: 0;
  flex-direction: column;
  border-left: 1px solid var(--color-border);
  background: var(--color-panel);
}

.paper-workspace__notes-header {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}

.paper-workspace__notes-title {
  margin: 0;
  font-size: 15px;
}

.paper-workspace__secondary {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 8px;
}

.paper-workspace__secondary:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.paper-workspace__brief {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.paper-workspace__brief-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.paper-workspace__brief-body {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.paper-workspace__brief-body h3 {
  margin: 10px 0 4px;
  color: var(--color-text);
  font-size: 12px;
}

.paper-workspace__brief-body p {
  margin: 0 0 6px;
}

.paper-workspace__tldr {
  color: var(--color-text);
  font-size: 13px !important;
  font-weight: 600;
}

.paper-workspace__brief-list {
  margin: 0 0 6px;
  padding-left: 18px;
}

.paper-workspace__note-compose {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}

.paper-workspace__textarea {
  resize: vertical;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  padding: 8px;
}

.paper-workspace__note-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.paper-workspace__empty {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.paper-note {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.paper-note__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.paper-note__type {
  border-radius: 999px;
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-size: 10px;
  padding: 2px 7px;
}

.paper-note__delete {
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 11px;
}

.paper-note__delete:hover {
  color: var(--color-danger);
}

.paper-note__quote {
  margin: 8px 0 0;
  padding-left: 8px;
  border-left: 2px solid var(--color-accent);
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.paper-note__content {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}

.paper-workspace__waiting {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--color-text-muted);
  font-size: 13px;
}

.paper-workspace__error {
  margin: 0;
  padding: 10px 26px;
  color: var(--color-danger);
  font-size: 12px;
}

@media (max-width: 980px) {
  .paper-workspace__body {
    grid-template-columns: 1fr;
  }

  .paper-workspace__notes {
    border-top: 1px solid var(--color-border);
    border-left: 0;
  }
}
</style>
