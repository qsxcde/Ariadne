<script setup lang="ts">
import { computed } from "vue";
import type { PaperSummary } from "@/api";
import { paperStatusLabel } from "@/shared/constants/paper";
import { formatAuthors, formatUpdatedAt, progressPercent } from "@/shared/utils/format";

const props = withDefaults(
  defineProps<{
    papers: PaperSummary[];
    selectedId?: string;
    checkedIds?: string[];
  }>(),
  {
    selectedId: "",
    checkedIds: () => [],
  },
);

const emit = defineEmits<{
  open: [paperId: string];
  markRead: [paperId: string];
  remove: [paperId: string];
  check: [paperId: string];
  checkAll: [];
}>();

const allChecked = computed(
  () =>
    props.papers.length > 0 &&
    props.papers.every((paper) => props.checkedIds.includes(paper.id)),
);
const someChecked = computed(() =>
  props.papers.some((paper) => props.checkedIds.includes(paper.id)),
);

function authorLine(paper: PaperSummary): string {
  const names = formatAuthors(paper.authors, { fallback: "" });
  const year = paper.year ? " · " + paper.year : "";
  if (names) {
    return names + year;
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
          <th class="library-table__check-col">
            <input
              type="checkbox"
              class="library-table__check"
              aria-label="选择当前列表全部论文"
              :checked="allChecked"
              :indeterminate.prop="someChecked && !allChecked"
              @change="emit('checkAll')"
            />
          </th>
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
          <td class="library-table__check-col">
            <input
              type="checkbox"
              class="library-table__check"
              :aria-label="`选择《${paper.title}》`"
              :checked="checkedIds.includes(paper.id)"
              @click.stop
              @change="emit('check', paper.id)"
            />
          </td>
          <td>
            <span class="library-table__status" :class="'is-' + paper.reading_status">
              <span class="library-table__dot" aria-hidden="true" />
              {{ paperStatusLabel(paper.reading_status) }}
            </span>
          </td>
          <td>
            <button type="button" class="library-table__title" @click.stop="emit('open', paper.id)">
              {{ paper.title }}
            </button>
          </td>
          <td class="library-table__meta library-table__author-col">{{ authorLine(paper) }}</td>
          <td class="library-table__meta library-table__venue-col">{{ paper.venue || "—" }}</td>
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
          <td class="library-table__meta library-table__read-col">{{ lastRead(paper) }}</td>
          <td class="library-table__tags-col">
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
                title="标记已读"
                @click.stop="emit('markRead', paper.id)"
              >
                已读
              </button>
              <button
                type="button"
                title="删除论文"
                @click.stop="emit('remove', paper.id)"
              >
                删除
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
  z-index: var(--z-sticky);
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

.library-table th.library-table__check-col,
.library-table td.library-table__check-col {
  width: 34px;
  padding-right: 4px;
  padding-left: 10px;
}

.library-table__check {
  width: 13px;
  height: 13px;
  margin: 0;
  accent-color: var(--color-accent);
  cursor: pointer;
}

.library-table__status-col {
  width: 68px;
}

.library-table__author-col {
  width: 16%;
}

.library-table__venue-col {
  width: 9%;
}

.library-table__progress-col {
  width: 96px;
}

.library-table__read-col {
  width: 84px;
}

.library-table__tags-col {
  width: 10%;
}

.library-table__actions-col {
  width: 118px;
}

/* 1024 断点：先让出标题宽度，再逐级隐藏低优先级列。 */
@media (max-width: 1200px) {
  .library-table__venue-col,
  .library-table__tags-col {
    display: none;
  }

  .library-table__author-col {
    width: 22%;
  }
}

@media (max-width: 1100px) {
  .library-table__read-col {
    display: none;
  }

  .library-table__author-col {
    width: 26%;
  }

  .library-table__actions-col {
    width: 110px;
  }
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
  box-shadow: inset 2px 0 var(--color-text);
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
  color: var(--color-aqua);
}

.library-table__status.is-reading .library-table__dot {
  background: var(--color-aqua);
}

.library-table__status.is-read {
  color: var(--color-success);
}

.library-table__status.is-read .library-table__dot {
  background: var(--color-success);
}

.library-table__status.is-skimming {
  color: var(--color-text-soft);
}

.library-table__status.is-skimming .library-table__dot {
  background: var(--color-text-soft);
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
  text-decoration: underline;
  text-decoration-color: var(--color-accent);
  text-underline-offset: 3px;
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
  background: var(--color-aqua);
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
  white-space: nowrap;
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
  color: var(--color-text-muted);
  font-size: 11px;
  white-space: nowrap;
}

.library-table__actions button:hover {
  color: var(--color-accent-strong);
}
</style>
