<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { updatePaper } from "../../../api/papers";
import type { PaperDetail, PaperUpdatePayload } from "../../../api";
import { toErrorMessage } from "../../../utils/error";

const props = defineProps<{
  visible: boolean;
  paper: PaperDetail | null;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
  "update:visible": [value: boolean];
}>();

const title = ref("");
const authorsText = ref("");
const year = ref("");
const venue = ref("");
const doi = ref("");
const arxivId = ref("");
const url = ref("");
const abstract = ref("");
const isSaving = ref(false);

const canSubmit = computed(() => title.value.trim().length > 0 && !isSaving.value);

watch(
  () => [props.visible, props.paper] as const,
  ([visible, paper]) => {
    if (!visible || !paper) {
      return;
    }
    title.value = paper.title ?? "";
    authorsText.value = (paper.authors ?? []).join(", ");
    year.value = paper.year ? String(paper.year) : "";
    venue.value = paper.venue ?? "";
    doi.value = paper.doi ?? "";
    arxivId.value = paper.arxiv_id ?? "";
    url.value = paper.url ?? "";
    abstract.value = paper.abstract ?? "";
  },
  { immediate: true },
);

function splitAuthors(value: string): string[] {
  return value
    .split(/[,，;；]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function closeDialog(): void {
  emit("update:visible", false);
  emit("close");
}

async function submit(): Promise<void> {
  if (!props.paper || !canSubmit.value) {
    return;
  }
  const parsedYear = Number.parseInt(year.value, 10);
  const payload: PaperUpdatePayload = {
    title: title.value.trim(),
    authors: splitAuthors(authorsText.value),
    year: Number.isFinite(parsedYear) ? parsedYear : null,
  };
  if (venue.value.trim()) payload.venue = venue.value.trim();
  if (doi.value.trim()) payload.doi = doi.value.trim();
  if (arxivId.value.trim()) payload.arxiv_id = arxivId.value.trim();
  if (url.value.trim()) payload.url = url.value.trim();
  if (abstract.value.trim()) payload.abstract = abstract.value.trim();

  isSaving.value = true;
  try {
    await updatePaper(props.paper.id, payload);
    ElMessage.success("已更新论文信息");
    emit("saved");
    closeDialog();
  } catch (error) {
    ElMessage.error(toErrorMessage(error, "更新论文信息失败"));
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <el-dialog :model-value="visible" title="编辑论文信息" width="560px" @close="closeDialog">
    <div class="metadata-form">
      <label class="metadata-form__field">
        <span>标题</span>
        <input v-model="title" type="text" maxlength="300" />
      </label>
      <label class="metadata-form__field">
        <span>作者（逗号分隔）</span>
        <input v-model="authorsText" type="text" placeholder="Ashish Vaswani, Noam Shazeer" />
      </label>
      <div class="metadata-form__row">
        <label class="metadata-form__field">
          <span>年份</span>
          <input v-model="year" type="number" min="1900" max="2100" />
        </label>
        <label class="metadata-form__field">
          <span>Venue</span>
          <input v-model="venue" type="text" placeholder="NeurIPS" />
        </label>
      </div>
      <div class="metadata-form__row">
        <label class="metadata-form__field">
          <span>DOI</span>
          <input v-model="doi" type="text" placeholder="10.1000/xyz" />
        </label>
        <label class="metadata-form__field">
          <span>arXiv ID</span>
          <input v-model="arxivId" type="text" placeholder="2401.00001" />
        </label>
      </div>
      <label class="metadata-form__field">
        <span>链接</span>
        <input v-model="url" type="url" placeholder="https://arxiv.org/abs/2401.00001" />
      </label>
      <label class="metadata-form__field">
        <span>摘要</span>
        <textarea v-model="abstract" rows="4" />
      </label>
    </div>
    <template #footer>
      <div class="metadata-form__footer">
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="isSaving" :disabled="!canSubmit" @click="submit">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.metadata-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
}

.metadata-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.metadata-form__field {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.metadata-form__field input,
.metadata-form__field textarea {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  padding: 7px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 13px;
}

.metadata-form__field textarea {
  resize: vertical;
}

.metadata-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
