<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { usePapers } from "@/features/library/composables/usePapers";
import type { AnnotationSummary } from "@/api";

const props = defineProps<{
  paperId: string;
}>();

const emit = defineEmits<{
  locate: [annotation: AnnotationSummary];
}>();

const { currentPaper, addNote, removeAnnotation } = usePapers();

const noteDraft = ref("");
const annotations = computed<AnnotationSummary[]>(() => currentPaper.value?.annotations ?? []);

function annotationLabel(annotation: AnnotationSummary): string {
  if (annotation.type === "highlight") return "高亮";
  if (annotation.type === "question") return "问题";
  return "笔记";
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

function exportNotes(): void {
  if (!currentPaper.value) return;
  const lines = [
    `# ${currentPaper.value.title}`,
    "",
    ...annotations.value.map((annotation) => {
      const quote = annotation.quote ? `> ${annotation.quote}\n\n` : "";
      const body = annotation.content ?? "";
      return `- [${annotationLabel(annotation)}] ${quote}${body}`.trim();
    }),
  ];
  const blob = new Blob([lines.join("\n")], {
    type: "text/markdown;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = `${currentPaper.value.title}-notes.md`;
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <div class="paper-workspace__notes-pane">
    <header class="paper-workspace__notes-head">
      <span>{{ annotations.length }} 条笔记</span>
      <button type="button" class="paper-workspace__secondary" @click="exportNotes">导出</button>
    </header>
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
      <p v-if="!annotations.length" class="paper-workspace__empty">
        还没有笔记。选中正文可快速记笔记。
      </p>
      <article v-for="annotation in annotations" :key="annotation.id" class="paper-note">
        <header class="paper-note__head">
          <div class="paper-note__meta">
            <span class="paper-note__type">{{ annotationLabel(annotation) }}</span>
            <span v-if="annotation.page_start" class="paper-note__page">
              p.{{ annotation.page_start }}
            </span>
          </div>
          <div class="paper-note__tools">
            <button
              v-if="annotation.chunk_id || annotation.page_start"
              type="button"
              class="paper-note__delete"
              @click="emit('locate', annotation)"
            >
              定位
            </button>
            <button type="button" class="paper-note__delete" @click="deleteNote(annotation)">
              删除
            </button>
          </div>
        </header>
        <blockquote v-if="annotation.quote" class="paper-note__quote">
          {{ annotation.quote }}
        </blockquote>
        <p v-if="annotation.content" class="paper-note__content">{{ annotation.content }}</p>
      </article>
    </div>
  </div>
</template>

<style scoped>
.paper-workspace__notes-pane {
  display: flex;
  flex-direction: column;
}

.paper-workspace__notes-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  padding: 10px 16px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.paper-workspace__secondary {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: var(--color-surface);
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 8px;
}

.paper-workspace__secondary:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.paper-workspace__primary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  color: var(--color-white);
  cursor: pointer;
  font-size: 11px;
  padding: 0 8px;
  height: 30px;
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
  border-radius: var(--radius-sm);
  background: var(--color-surface);
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

.paper-note__meta,
.paper-note__tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

.paper-note__page {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.paper-note__type {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--color-text-muted);
  font-size: 10px;
  padding: 1px 6px;
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
</style>
