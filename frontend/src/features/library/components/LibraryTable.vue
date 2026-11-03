<script setup lang="ts">
import type { PaperSummary } from "../../../api";
import { formatUpdatedAt } from "../../../utils/format";

withDefaults(
  defineProps<{
    papers: PaperSummary[];
    selectedId?: string;
  }>(),
  {
    selectedId: "",
  },
);

const emit = defineEmits<{
  open: [paperId: string];
  markRead: [paperId: string];
}>();

const STATUS_LABELS: Record<string, string> = {
  inbox: "待读",
  queued: "队列",
  skimming: "速读",
  reading: "在读",
  read: "已读",
  archived: "归档",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function progressPercent(progress: number): number {
  return Math.round(Math.max(0, Math.min(1, progress)) * 100);
}

function authorLine(paper: PaperSummary): string {
  const authors = paper.authors ?? [];
  const names = authors.slice(0, 3).join("、");
  const suffix = authors.length > 3 ? " 等" : "";
  const year = paper.year ? " · " + paper.year : "";
  if (names) {
    return names + suffix + year;
  }
  return paper.year ? String(paper.year) : "—";
}

function lastRead(paper: PaperSummary): string {
  return paper.last_read_at ? formatUpdatedAt(paper.last_read_at) : "—";
}

function visibleTags(paper: PaperSummary): string[] {
  return (paper.tags ?? []).slice(0, 2);
}
</script>

<template>
  <div class="library-table-wrap">
    <table class="library-table">
      <thead>
        <tr>
          <th class="library-table__status-col">状态</th>
          <th>标题</th>
          <th class="library-table__author-col">作者 / 年份</th>
          <th class="library-table__venue-col">Venue</th>
          <th class="library-table__progress-col">进度</th>
          <th class="library-table__read-col">最后阅读</th>
          <th class="library-table__tags-col">标签</th>
          <th class="library-table__actions-col" aria-label="操作"></th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="paper in papers"
          :key="paper.id"
          class="library-table__row"
          :class="{ 'is-selected': paper.id === selectedId }"
          @click="emit('open', paper.id)"
        >
          <td>
            <span class="library-table__status" :class="'is-' + paper.reading_status">
              <span class="library-table__dot" aria-hidden="true" />
              {{ statusLabel(paper.reading_status) }}
            </span>
          </td>
          <td>
            <button type="button" class="library-table__title" @click.stop="emit('open', paper.id)">
              {{ paper.title }}
            </button>
          </td>
          <td class="library-table__meta">{{ authorLine(paper) }}</td>
          <td class="library-table__meta">{{ paper.venue || "—" }}</td>
          <td>
            <div class="library-table__progress">
              <span class="library-table__track" aria-hidden="true">
                <span
                  class="library-table__fill"
                  :style="{ width: progressPercent(paper.progress) + '%' }"
                />
              </span>
              <span class="library-table__pct">{{ progressPercent(paper.progress) }}%</span>
            </div>
          </td>
          <td class="library-table__meta">{{ lastRead(paper) }}</td>
          <td>
            <span v-if="!(paper.tags ?? []).length" class="library-table__meta">—</span>
            <span v-else class="library-table__tags">
              <span v-for="tag in visibleTags(paper)" :key="tag" class="library-table__tag">
                {{ tag }}
              </span>
              <span v-if="(paper.tags ?? []).length > 2" class="library-table__tag">
                +{{ (paper.tags ?? []).length - 2 }}
              </span>
            </span>
          </td>
          <td>
            <div class="library-table__actions">
              <button type="button" @click.stop="emit('open', paper.id)">打开</button>
              <button
                v-if="paper.reading_status !== 'read'"
                type="button"
                @click.stop="emit('markRead', paper.id)"
              >
                标记已读
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.library-table-wrap {
  min-height: 0;
  flex: 1;
  overflow: auto;
  border-top: 1px solid var(--color-border);
}

.library-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 12px;
}

.library-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-page);
  padding: 8px 10px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-align: left;
  text-transform: uppercase;
}

.library-table__status-col {
  width: 76px;
}

.library-table__author-col {
  width: 20%;
}

.library-table__venue-col {
  width: 11%;
}

.library-table__progress-col {
  width: 110px;
}

.library-table__read-col {
  width: 92px;
}

.library-table__tags-col {
  width: 12%;
}

.library-table__actions-col {
  width: 108px;
}

.library-table__row {
  height: 46px;
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
}

.library-table__row:hover,
.library-table__row.is-selected {
  background: var(--color-surface);
}

.library-table__row.is-selected {
  box-shadow: inset 2px 0 var(--color-accent);
}

.library-table td {
  overflow: hidden;
  padding: 6px 10px;
  vertical-align: middle;
}

.library-table__status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--color-text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.library-table__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.library-table__status.is-reading {
  color: var(--color-accent);
}

.library-table__status.is-reading .library-table__dot {
  background: var(--color-accent);
}

.library-table__status.is-read {
  color: var(--color-success);
}

.library-table__status.is-read .library-table__dot {
  background: var(--color-success);
}

.library-table__status.is-skimming {
  color: var(--color-aqua);
}

.library-table__status.is-skimming .library-table__dot {
  background: var(--color-aqua);
}

.library-table__title {
  display: block;
  width: 100%;
  overflow: hidden;
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 13.5px;
  font-weight: 600;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.library-table__row:hover .library-table__title {
  color: var(--color-accent-strong);
}

.library-table__meta {
  overflow: hidden;
  color: var(--color-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.library-table__progress {
  display: flex;
  align-items: center;
  gap: 6px;
}

.library-table__track {
  display: block;
  height: 3px;
  flex: 1;
  overflow: hidden;
  background: var(--color-surface-muted);
}

.library-table__fill {
  display: block;
  height: 100%;
  background: var(--color-accent);
}

.library-table__pct {
  width: 30px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-align: right;
}

.library-table__tags {
  display: flex;
  gap: 4px;
  overflow: hidden;
}

.library-table__tag {
  border: 1px solid var(--color-border);
  padding: 1px 5px;
  color: var(--color-text-muted);
  font-size: 10px;
  white-space: nowrap;
}

.library-table__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  opacity: 0;
  transition: opacity var(--motion-fast) var(--ease-out);
}

.library-table__row:hover .library-table__actions,
.library-table__row.is-selected .library-table__actions,
.library-table__row:focus-within .library-table__actions {
  opacity: 1;
}

.library-table__actions button {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-accent);
  font-size: 11px;
}
</style>
