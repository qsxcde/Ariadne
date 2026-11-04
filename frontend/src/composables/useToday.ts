import { computed, ref } from "vue";
import { ElMessage } from "element-plus";

import { usePapers } from "./usePapers";
import { getLibraryStats, getWeeklyReview, saveWeeklyNote } from "../api/papers";
import type { LibraryStats, PaperSummary, WeeklyReview } from "../api";

const { papers, loadLibrary } = usePapers();

const review = ref<WeeklyReview | null>(null);
const stats = ref<LibraryStats | null>(null);
const weeklyNote = ref("");
const isSavingNote = ref(false);

const reading = computed(() =>
  papers.value
    .filter((paper) => paper.reading_status === "reading")
    .sort((a, b) => (b.last_read_at ?? "").localeCompare(a.last_read_at ?? "")),
);
const readingPreview = computed(() => reading.value.slice(0, 5));
const queue = computed(() =>
  papers.value
    .filter((paper) => paper.reading_status === "queued" || paper.reading_status === "inbox")
    .slice(0, 12),
);
const readThisWeek = computed(() => review.value?.read_papers ?? 0);
const notesThisWeek = computed(() => review.value?.notes ?? 0);
const openQuestions = computed(() => review.value?.open_questions ?? 0);
const todayLabel = computed(() =>
  new Date().toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
  }),
);

function progressPercent(paper: PaperSummary): number {
  return Math.round(Math.max(0, Math.min(1, paper.progress)) * 100);
}

function authorLine(paper: PaperSummary): string {
  const names = (paper.authors ?? []).slice(0, 3).join("、");
  const year = paper.year ? " · " + paper.year : "";
  const venue = paper.venue ? " · " + paper.venue : "";
  return (names || "未知作者") + year + venue;
}

async function load(): Promise<void> {
  await loadLibrary();
  try {
    [review.value, stats.value] = await Promise.all([getWeeklyReview(), getLibraryStats()]);
  } catch {
    review.value = null;
    stats.value = null;
  }
  weeklyNote.value = review.value?.note ?? "";
}

async function saveNote(): Promise<void> {
  isSavingNote.value = true;
  try {
    review.value = await saveWeeklyNote(weeklyNote.value);
    weeklyNote.value = review.value.note ?? "";
    ElMessage.success("已保存本周复盘");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "保存复盘失败");
  } finally {
    isSavingNote.value = false;
  }
}

export function useToday() {
  return {
    papers,
    review,
    stats,
    weeklyNote,
    isSavingNote,
    reading,
    readingPreview,
    queue,
    readThisWeek,
    notesThisWeek,
    openQuestions,
    todayLabel,
    progressPercent,
    authorLine,
    load,
    saveNote,
  };
}
