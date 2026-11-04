import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import { askCollection, compareCollectionPapers } from "@/api/synthesis";
import { listCollections } from "@/api/collections";
import { listPapers } from "@/api/papers";
import type {
  CollectionAskResult,
  CollectionSummary,
  PaperComparison,
  PaperSummary,
} from "@/api";
import { toErrorMessage } from "@/shared/utils/error";

export const SYNTHESIS_TABS = [
  { value: "ask", label: "问答" },
  { value: "compare", label: "对比表" },
  { value: "matrix", label: "综述矩阵" },
] as const;

export const MATRIX_FIELDS = [
  { key: "method", label: "方法" },
  { key: "datasets", label: "数据集" },
  { key: "metrics", label: "指标" },
  { key: "limitations", label: "局限" },
] as const;

const collections = ref<CollectionSummary[]>([]);
const selectedCollectionId = ref("");
const papers = ref<PaperSummary[]>([]);
const selectedPaperIds = ref<string[]>([]);
const question = ref("");
const answer = ref<CollectionAskResult | null>(null);
const comparison = ref<PaperComparison[]>([]);
const isLoading = ref(false);
const isAsking = ref(false);
const isComparing = ref(false);
const errorMessage = ref("");

const fieldCoverage = computed(() =>
  MATRIX_FIELDS.map((field) => ({
    ...field,
    covered: comparison.value.filter((row) => {
      const value = (row[field.key] ?? "").trim();
      return value.length > 0 && value !== "未提及";
    }).length,
  })),
);

const selectedCollection = computed(
  () => collections.value.find((item) => item.id === selectedCollectionId.value) ?? null,
);

async function loadCollections(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    collections.value = await listCollections();
    if (!selectedCollectionId.value && collections.value.length) {
      selectedCollectionId.value = collections.value[0].id;
      await loadPapers();
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "读取集合失败");
  } finally {
    isLoading.value = false;
  }
}

async function loadPapers(): Promise<void> {
  if (!selectedCollectionId.value) {
    papers.value = [];
    return;
  }
  try {
    papers.value = await listPapers({ collectionId: selectedCollectionId.value });
    selectedPaperIds.value = [];
    answer.value = null;
    comparison.value = [];
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "读取集合论文失败");
  }
}

function togglePaper(paperId: string): void {
  if (selectedPaperIds.value.includes(paperId)) {
    selectedPaperIds.value = selectedPaperIds.value.filter((id) => id !== paperId);
  } else if (selectedPaperIds.value.length < 5) {
    selectedPaperIds.value = [...selectedPaperIds.value, paperId];
  }
}

async function ask(): Promise<void> {
  if (!selectedCollectionId.value || !question.value.trim()) {
    return;
  }
  isAsking.value = true;
  errorMessage.value = "";
  try {
    answer.value = await askCollection(selectedCollectionId.value, question.value.trim());
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "集合问答失败");
  } finally {
    isAsking.value = false;
  }
}

async function compare(): Promise<void> {
  if (selectedPaperIds.value.length < 2) {
    ElMessage.warning("至少选择 2 篇论文");
    return;
  }
  isComparing.value = true;
  errorMessage.value = "";
  try {
    comparison.value = await compareCollectionPapers(
      selectedCollectionId.value,
      selectedPaperIds.value,
    );
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "论文对比失败");
  } finally {
    isComparing.value = false;
  }
}

function download(content: string, filename: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportComparison(): void {
  if (!comparison.value.length) return;
  const header = ["论文", "方法", "数据集", "指标", "局限"];
  const rows = comparison.value.map((row) => [
    row.title,
    row.method,
    row.datasets,
    row.metrics,
    row.limitations,
  ]);
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  download(csv, "paper-comparison.csv", "text/csv;charset=utf-8");
}

function escapeMarkdownCell(value: string): string {
  return String(value ?? "")
    .replaceAll("|", "\\|")
    .replaceAll("\n", " ")
    .trim();
}

function exportMatrixMarkdown(): void {
  if (!comparison.value.length) {
    return;
  }
  const header = `| 论文 | ${MATRIX_FIELDS.map((field) => field.label).join(" | ")} |`;
  const separator = `| --- | ${MATRIX_FIELDS.map(() => "---").join(" | ")} |`;
  const rows = comparison.value.map(
    (row) =>
      `| ${[row.title, ...MATRIX_FIELDS.map((field) => row[field.key])]
        .map(escapeMarkdownCell)
        .join(" | ")} |`,
  );
  const coverage = `\n覆盖：${fieldCoverage.value
    .map((field) => `${field.label} ${field.covered}/${comparison.value.length}`)
    .join(" · ")}`;
  const markdown = [header, separator, ...rows, coverage].join("\n");
  download(markdown, "survey-matrix.md", "text/markdown;charset=utf-8");
}

export function useSynthesis() {
  return {
    collections,
    selectedCollectionId,
    selectedCollection,
    papers,
    selectedPaperIds,
    question,
    answer,
    comparison,
    fieldCoverage,
    isLoading,
    isAsking,
    isComparing,
    errorMessage,
    loadCollections,
    loadPapers,
    togglePaper,
    ask,
    compare,
    exportComparison,
    exportMatrixMarkdown,
  };
}
