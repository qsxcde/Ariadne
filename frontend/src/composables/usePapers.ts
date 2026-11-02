import { computed, ref } from "vue";
import { listCollections } from "../api/collections";
import { createAnnotation, deleteAnnotation } from "../api/annotations";
import { getPaper, getPaperBrief, listPapers, updatePaper, uploadPaper } from "../api/papers";
import type {
  AnnotationSummary,
  CollectionSummary,
  PaperBrief,
  PaperDetail,
  PaperSummary,
  PaperUpdatePayload,
} from "../api";
import { toErrorMessage } from "../utils/error";

export type PaperFilters = {
  status: string;
  collectionId: string;
  tag: string;
  query: string;
};

const papers = ref<PaperSummary[]>([]);
const currentPaper = ref<PaperDetail | null>(null);
const brief = ref<PaperBrief | null>(null);
const collections = ref<CollectionSummary[]>([]);
const filters = ref<PaperFilters>({
  status: "",
  collectionId: "",
  tag: "",
  query: "",
});
const isLoading = ref(false);
const isUploading = ref(false);
const isBriefLoading = ref(false);
const errorMessage = ref("");

const paperCount = computed(() => papers.value.length);
const readingCount = computed(
  () => papers.value.filter((paper) => paper.reading_status === "reading").length,
);

async function loadLibrary(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const [items, collectionItems] = await Promise.all([
      listPapers({
        status: filters.value.status || undefined,
        collectionId: filters.value.collectionId || undefined,
        tag: filters.value.tag || undefined,
        query: filters.value.query || undefined,
      }),
      listCollections(),
    ]);
    papers.value = items;
    collections.value = collectionItems;
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "读取文献库失败");
  } finally {
    isLoading.value = false;
  }
}

async function loadPaper(paperId: string): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    currentPaper.value = await getPaper(paperId);
  } catch (error) {
    currentPaper.value = null;
    errorMessage.value = toErrorMessage(error, "读取论文失败");
  } finally {
    isLoading.value = false;
  }
}

async function loadBrief(paperId: string, force = false): Promise<void> {
  isBriefLoading.value = true;
  errorMessage.value = "";
  try {
    brief.value = await getPaperBrief(paperId, force);
  } catch (error) {
    brief.value = null;
    errorMessage.value = toErrorMessage(error, "生成速读卡失败");
  } finally {
    isBriefLoading.value = false;
  }
}

async function saveReadingState(
  paperId: string,
  payload: PaperUpdatePayload,
): Promise<void> {
  try {
    const updated = await updatePaper(paperId, payload);
    currentPaper.value = updated;
    const index = papers.value.findIndex((paper) => paper.id === paperId);
    if (index >= 0) {
      papers.value[index] = {
        ...papers.value[index],
        reading_status: updated.reading_status,
        progress: updated.progress,
        last_read_at: updated.last_read_at,
        updated_at: updated.updated_at,
      };
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "保存阅读进度失败");
  }
}

async function addNote(
  paperId: string,
  content: string,
  quote?: string,
): Promise<AnnotationSummary | null> {
  try {
    const annotation = await createAnnotation(paperId, {
      type: quote ? "highlight" : "note",
      content: content || undefined,
      quote: quote || undefined,
    });
    if (currentPaper.value) {
      currentPaper.value.annotations = [
        ...(currentPaper.value.annotations ?? []),
        annotation,
      ];
    }
    return annotation;
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "保存笔记失败");
    return null;
  }
}

async function removeAnnotation(annotationId: string): Promise<void> {
  try {
    await deleteAnnotation(annotationId);
    if (currentPaper.value) {
      currentPaper.value.annotations = (currentPaper.value.annotations ?? []).filter(
        (annotation) => annotation.id !== annotationId,
      );
    }
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "删除笔记失败");
  }
}

async function upload(file: File): Promise<PaperSummary | null> {
  isUploading.value = true;
  errorMessage.value = "";
  try {
    const result = await uploadPaper(file);
    await loadLibrary();
    return result.paper;
  } catch (error) {
    errorMessage.value = toErrorMessage(error, "上传论文失败");
    return null;
  } finally {
    isUploading.value = false;
  }
}

function reset(): void {
  papers.value = [];
  currentPaper.value = null;
  brief.value = null;
  collections.value = [];
  filters.value = { status: "", collectionId: "", tag: "", query: "" };
  isLoading.value = false;
  isUploading.value = false;
  isBriefLoading.value = false;
  errorMessage.value = "";
}

export function usePapers() {
  return {
    papers,
    currentPaper,
    brief,
    collections,
    filters,
    isLoading,
    isUploading,
    isBriefLoading,
    errorMessage,
    paperCount,
    readingCount,
    loadLibrary,
    loadPaper,
    loadBrief,
    saveReadingState,
    addNote,
    removeAnnotation,
    upload,
    reset,
  };
}
