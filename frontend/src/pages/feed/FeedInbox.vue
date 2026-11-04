<script setup lang="ts">
import StateBlock from "@/shared/components/StateBlock.vue";
import { FEED_STATUS_OPTIONS, useFeed } from "@/pages/feed/useFeed";
import type { FeedItemSummary } from "@/api";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const { items, isLoading, statusFilter, selectedIndex, selectStatus, selectRow, save, ignore } =
  useFeed();

function openPaper(item: FeedItemSummary): void {
  if (item.paper_id) {
    emit("open", item.paper_id);
  }
}

async function saveItem(item: FeedItemSummary): Promise<void> {
  const paperId = await save(item);
  if (paperId) {
    emit("open", paperId);
  }
}
</script>

<template>
  <section class="feed-view__inbox">
    <div class="feed-view__inbox-head">
      <div class="feed-view__filters" role="tablist" aria-label="Feed 状态">
        <button
          v-for="option in FEED_STATUS_OPTIONS"
          :key="option.value"
          type="button"
          role="tab"
          class="feed-view__filter"
          :class="{ 'is-active': statusFilter === option.value }"
          :aria-selected="statusFilter === option.value"
          @click="selectStatus(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
      <span class="feed-view__hint">J/K 移动 · S 保存 · X 忽略 · Enter 打开</span>
    </div>

    <StateBlock v-if="isLoading" kind="loading" description="正在读取 Feed…" />
    <StateBlock
      v-else-if="!items.length"
      kind="empty"
      title="没有待处理内容"
      description="添加订阅后点「刷新 Feed」，新论文会进入这里。"
    />

    <div v-else class="feed-view__list">
      <article
        v-for="(item, index) in items"
        :key="item.id"
        class="feed-row"
        :class="{ 'is-selected': index === selectedIndex }"
        @click="selectRow(index)"
        @dblclick="item.paper_id ? openPaper(item) : saveItem(item)"
      >
        <span class="feed-row__source">{{ item.source }}</span>
        <div class="feed-row__main">
          <h3 class="feed-row__title">{{ item.title }}</h3>
          <p class="feed-row__meta">
            <span>{{ (item.authors ?? []).slice(0, 3).join("、") || "未知作者" }}</span>
            <span v-if="item.published_at"> · {{ item.published_at.slice(0, 10) }}</span>
            <span class="feed-row__reason"> · {{ item.relevance_reason }}</span>
          </p>
        </div>
        <div class="feed-row__actions">
          <button v-if="item.status === 'new'" type="button" @click.stop="saveItem(item)">
            保存
          </button>
          <button v-if="item.status === 'new'" type="button" @click.stop="ignore(item)">
            忽略
          </button>
          <button v-if="item.paper_id" type="button" @click.stop="openPaper(item)">打开</button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.feed-view__inbox {
  min-width: 0;
}

.feed-view__inbox-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 0;
}

.feed-view__filters {
  display: flex;
  gap: 16px;
}

.feed-view__filter {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  padding: 4px 1px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.feed-view__filter.is-active {
  border-bottom-color: var(--color-text);
  color: var(--color-text);
  font-weight: 600;
}

.feed-view__hint {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.feed-view__list {
  display: flex;
  flex-direction: column;
}

.feed-row {
  display: flex;
  align-items: center;
  gap: 14px;
  border-bottom: 1px solid var(--color-border);
  border-left: 2px solid transparent;
  padding: 11px 10px 11px 12px;
  cursor: pointer;
}

.feed-row:hover,
.feed-row.is-selected {
  background: var(--color-surface);
}

.feed-row.is-selected {
  border-left-color: var(--color-accent);
}

.feed-row__source {
  width: 58px;
  flex: 0 0 58px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.feed-row__main {
  min-width: 0;
  flex: 1;
}

.feed-row__title {
  margin: 0 0 3px;
  overflow: hidden;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-row__meta {
  margin: 0;
  overflow: hidden;
  color: var(--color-text-muted);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-row__reason {
  color: var(--color-text-muted);
}

.feed-row__actions {
  display: flex;
  gap: 10px;
  opacity: 0;
  transition: opacity var(--motion-fast) var(--ease-out);
}

.feed-row:hover .feed-row__actions,
.feed-row.is-selected .feed-row__actions {
  opacity: 1;
}

.feed-row__actions button {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 10px;
}

.feed-row__actions button:hover {
  color: var(--color-text);
}
</style>
