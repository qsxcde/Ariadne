<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { importPaperByReference } from "../../../api/papers";
import type { PaperImportPayload } from "../../../api";
import { toErrorMessage } from "../../../utils/error";

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  close: [];
  imported: [paperId: string];
  "update:visible": [value: boolean];
}>();

type ImportSource = PaperImportPayload["source"];

const SOURCE_OPTIONS: { value: ImportSource; label: string; placeholder: string }[] = [
  { value: "arxiv", label: "arXiv", placeholder: "2401.00001 或 https://arxiv.org/abs/…" },
  { value: "doi", label: "DOI", placeholder: "10.1000/xyz 或 https://doi.org/…" },
  { value: "url", label: "网页链接", placeholder: "https://example.org/paper" },
];

const source = ref<ImportSource>("arxiv");
const identifier = ref("");
const downloadPdf = ref(true);
const isSubmitting = ref(false);

const placeholder = computed(
  () => SOURCE_OPTIONS.find((option) => option.value === source.value)?.placeholder ?? "",
);

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      return;
    }
    source.value = "arxiv";
    identifier.value = "";
    downloadPdf.value = true;
  },
);

function closeDialog(): void {
  emit("update:visible", false);
  emit("close");
}

async function submit(): Promise<void> {
  const value = identifier.value.trim();
  if (!value) {
    ElMessage.warning("请输入标识或链接");
    return;
  }
  isSubmitting.value = true;
  try {
    const result = await importPaperByReference({
      source: source.value,
      identifier: value,
      download_pdf: downloadPdf.value,
    });
    ElMessage.success(
      result.pdf_imported
        ? `已导入《${result.paper.title}》`
        : `已导入《${result.paper.title}》元数据`,
    );
    if (result.warning) {
      ElMessage.info(result.warning);
    }
    emit("imported", result.paper.id);
    closeDialog();
  } catch (error) {
    ElMessage.error(toErrorMessage(error, "导入论文失败"));
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <el-dialog :model-value="visible" title="按标识导入" width="460px" @close="closeDialog">
    <div class="paper-import">
      <label class="paper-import__label" for="paper-import-source">来源</label>
      <select id="paper-import-source" v-model="source" class="paper-import__select">
        <option v-for="option in SOURCE_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>

      <label class="paper-import__label" for="paper-import-identifier">标识 / 链接</label>
      <input
        id="paper-import-identifier"
        v-model="identifier"
        class="paper-import__input"
        type="text"
        :placeholder="placeholder"
        @keyup.enter="submit"
      />

      <label class="paper-import__checkbox">
        <input v-model="downloadPdf" type="checkbox" />
        有开放 PDF 时自动下载并解析
      </label>

      <p class="paper-import__hint">
        arXiv 会抓取题录并下载 PDF；DOI 通过 Crossref 取元数据，无开放 PDF
        时只入库题录；网页链接会读取 citation 元标签。
      </p>
    </div>
    <template #footer>
      <div class="paper-import__footer">
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :loading="isSubmitting" @click="submit">导入</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.paper-import {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 6px;
}

.paper-import__label {
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-import__select,
.paper-import__input {
  min-height: 38px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  padding: 0 10px;
  color: var(--color-text);
  font-size: 13px;
}

.paper-import__checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.paper-import__hint {
  margin: 4px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.paper-import__footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
