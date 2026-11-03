<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import StateBlock from "../components/StateBlock.vue";
import { usePapers } from "../composables/usePapers";
import { getLibraryStats, getWeeklyReview, saveWeeklyNote } from "../api/papers";
import { formatDuration } from "../utils/format";
import type { LibraryStats, PaperSummary, WeeklyReview } from "../api";

const emit = defineEmits<{
  open: [paperId: string];
  library: [];
  settings: [];
}>();

const { papers, isLoading, errorMessage, loadLibrary } = usePapers();
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

function openPaper(paper: PaperSummary): void {
  emit("open", paper.id);
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

onMounted(async () => {
  await loadLibrary();
  try {
    [review.value, stats.value] = await Promise.all([
      getWeeklyReview(),
      getLibraryStats(),
    ]);
  } catch {
    review.value = null;
    stats.value = null;
  }
  weeklyNote.value = review.value?.note ?? "";
});
</script>

<template>
  <section class="today" aria-label="Today">
    <header class="today__bar">
      <div>
        <p class="today__eyebrow">{{ todayLabel }} · 文献库 {{ papers.length }} 篇</p>
        <h1 class="today__title">今天读什么</h1>
        <p class="today__subtitle">继续上次的阅读，或从队列里挑一篇。</p>
      </div>
    </header>

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取失败"
      :description="errorMessage"
      compact
    />
    <StateBlock
      v-if="isLoading && !papers.length"
      kind="loading"
      description="正在读取阅读进度…"
    />

    <div class="today__columns">
      <section class="today__reading">
        <header class="today__section-head">
          <h2>继续阅读</h2>
          <div class="today__head-actions">
            <span>{{ reading.length }} 篇在读</span>
            <button
              v-if="reading.length"
              type="button"
              class="today__primary today__primary--small"
              @click="openPaper(reading[0])"
            >
              继续上次阅读
            </button>
          </div>
        </header>

        <StateBlock
          v-if="!reading.length"
          kind="empty"
          compact
          title="还没有在读的论文"
          description="去文献库打开一篇，阅读进度会自动记录。"
          action-label="去文献库"
          @action="emit('library')"
        />

        <article
          v-for="(paper, index) in readingPreview"
          :key="paper.id"
          class="reading-item"
          tabindex="0"
          role="button"
          @click="openPaper(paper)"
          @keyup.enter="openPaper(paper)"
        >
          <span class="reading-item__index">{{ String(index + 1).padStart(2, "0") }}</span>
          <div class="reading-item__main">
            <h3 class="reading-item__title">{{ paper.title }}</h3>
            <p class="reading-item__meta">{{ authorLine(paper) }}</p>
            <div class="reading-item__track" aria-hidden="true">
              <span :style="{ width: progressPercent(paper) + '%' }" />
            </div>
          </div>
          <span class="reading-item__pct">{{ progressPercent(paper) }}%</span>
        </article>

        <p v-if="reading.length > 5" class="today__more">
          还有 {{ reading.length - 5 }} 篇在读，去文献库查看全部。
        </p>
      </section>

      <aside class="today__week">
        <header class="today__section-head">
          <h2>本周</h2>
          <span>目标 3 篇</span>
        </header>

        <p class="today__metric">
          {{ readThisWeek }}<small> / 3 篇读完</small>
        </p>

        <dl class="today__stats">
          <div>
            <dt>笔记</dt>
            <dd>{{ notesThisWeek }}</dd>
          </div>
          <div>
            <dt>开放问题</dt>
            <dd>{{ openQuestions }}</dd>
          </div>
          <div>
            <dt>本周阅读</dt>
            <dd>{{ formatDuration(stats?.reading_seconds_week ?? 0) }}</dd>
          </div>
          <div>
            <dt>今日阅读</dt>
            <dd>{{ formatDuration(stats?.reading_seconds_today ?? 0) }}</dd>
          </div>
        </dl>

        <label class="today__note">
          <span>本周复盘</span>
          <textarea
            v-model="weeklyNote"
            rows="5"
            maxlength="5000"
            placeholder="这周读完什么、卡在哪里、下周读什么…"
          />
        </label>
        <button
          type="button"
          class="today__save"
          :disabled="isSavingNote"
          @click="saveNote"
        >
          {{ isSavingNote ? "保存中…" : "保存复盘" }}
        </button>
      </aside>
    </div>

    <section class="today__queue">
      <header class="today__section-head">
        <h2>阅读队列</h2>
        <span>{{ queue.length }} 篇</span>
      </header>
      <StateBlock
        v-if="!queue.length"
        kind="empty"
        compact
        description="队列是空的。把想读的论文标记为「队列中」即可出现在这里。"
      />
      <div v-else class="today__queue-track">
        <button
          v-for="paper in queue"
          :key="paper.id"
          type="button"
          class="queue-item"
          @click="openPaper(paper)"
        >
          <span class="queue-item__status">
            {{ paper.reading_status === "queued" ? "队列" : "待读" }}
          </span>
          <span class="queue-item__title">{{ paper.title }}</span>
          <span class="queue-item__meta">{{ authorLine(paper) }}</span>
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.today {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 26px;
  padding: 26px max(30px, calc((100% - 1320px) / 2)) 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.today__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
}

.today__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.today__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.today__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.today__primary {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 8px 16px;
  color: var(--color-white);
  font-size: 12px;
  letter-spacing: 0.03em;
}

.today__primary:hover {
  background: var(--color-accent-strong);
}

.today__primary--small {
  padding: 4px 10px;
  font-size: 11px;
}

.today__head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.today__columns {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 1fr);
  gap: 34px;
}

.today__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.today__section-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.today__section-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.today__reading {
  min-width: 0;
}

.reading-item {
  display: flex;
  align-items: center;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 2px;
  cursor: pointer;
}

.reading-item:last-of-type {
  border-bottom: 0;
}

.reading-item:hover .reading-item__title {
  text-decoration: underline;
  text-decoration-color: var(--color-accent);
  text-underline-offset: 3px;
}

.reading-item__index {
  color: var(--color-border-strong);
  font-family: var(--font-mono);
  font-size: 11px;
}

.reading-item__main {
  min-width: 0;
  flex: 1;
}

.reading-item__title {
  margin: 0 0 5px;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-item__meta {
  margin: 0 0 9px;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reading-item__track {
  height: 3px;
  overflow: hidden;
  background: var(--color-surface-muted);
}

.reading-item__track span {
  display: block;
  height: 100%;
  background: var(--color-aqua);
}

.reading-item__pct {
  width: 38px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
  text-align: right;
}

.today__more {
  margin: 10px 0 0;
  color: var(--color-text-muted);
  font-size: 11px;
}

.today__week {
  min-width: 0;
  border-left: 1px solid var(--color-border);
  padding-left: 28px;
}

.today__metric {
  margin: 4px 0 14px;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 38px;
  font-weight: 650;
  line-height: 1;
}

.today__metric small {
  color: var(--color-text-muted);
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 400;
}

.today__stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 18px;
  margin: 0 0 18px;
}

.today__stats div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.today__stats dt {
  color: var(--color-text-muted);
  font-size: 10px;
}

.today__stats dd {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-mono);
  font-size: 13px;
}

.today__note {
  display: flex;
  flex-direction: column;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
}

.today__note textarea {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 8px 9px;
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  line-height: 1.6;
  resize: vertical;
}

.today__save {
  margin-top: 8px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 12px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.today__save:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.today__save:disabled {
  opacity: 0.6;
}

.today__queue {
  min-width: 0;
}

.today__queue-track {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  border-top: 1px solid var(--color-border);
}

.queue-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 5px;
  border: 0;
  border-right: 1px solid var(--color-border);
  border-bottom: 1px solid var(--color-border);
  background: transparent;
  padding: 12px 16px;
  text-align: left;
}

.queue-item:hover {
  background: var(--color-surface);
}

.queue-item__status {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.queue-item__title {
  display: -webkit-box;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.queue-item__meta {
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.today__empty,
.today__state {
  color: var(--color-text-muted);
  font-size: 12px;
}

.today__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
}

@media (max-width: 1100px) {
  .today__columns {
    grid-template-columns: 1fr;
  }

  .today__week {
    border-left: 0;
    border-top: 1px solid var(--color-border);
    padding: 18px 0 0;
  }
}
</style>
