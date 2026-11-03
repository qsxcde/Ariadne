<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import StateBlock from "../components/StateBlock.vue";
import {
  createSubscription,
  deleteSubscription,
  ignoreFeedItem,
  listFeed,
  listSubscriptions,
  refreshFeed,
  saveFeedItem,
} from "../api/feed";
import type { FeedItemSummary, SubscriptionCreatePayload, SubscriptionSummary } from "../api";

const emit = defineEmits<{
  open: [paperId: string];
}>();

const subscriptions = ref<SubscriptionSummary[]>([]);
const items = ref<FeedItemSummary[]>([]);
const kind = ref<SubscriptionCreatePayload["kind"]>("keyword");
const source = ref<SubscriptionCreatePayload["source"]>("arxiv");
const value = ref("");
const statusFilter = ref("new");
const selectedIndex = ref(0);
const isLoading = ref(false);
const isRefreshing = ref(false);
const errorMessage = ref("");

const KIND_OPTIONS = [
  { value: "keyword", label: "关键词" },
  { value: "author", label: "作者" },
  { value: "venue", label: "会议/期刊" },
  { value: "institution", label: "机构" },
];

const SOURCE_OPTIONS = [
  { value: "arxiv", label: "arXiv" },
  { value: "openalex", label: "OpenAlex" },
  { value: "pubmed", label: "PubMed" },
  { value: "rss", label: "RSS" },
];

const STATUS_OPTIONS = [
  { value: "new", label: "未处理" },
  { value: "saved", label: "已保存" },
  { value: "ignored", label: "已忽略" },
  { value: "", label: "全部" },
];

async function load(): Promise<void> {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const [subs, feed] = await Promise.all([
      listSubscriptions(),
      listFeed(statusFilter.value || undefined),
    ]);
    subscriptions.value = subs;
    items.value = feed;
    selectedIndex.value = Math.min(selectedIndex.value, Math.max(0, feed.length - 1));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取 Feed 失败";
  } finally {
    isLoading.value = false;
  }
}

function selectStatus(status: string): void {
  statusFilter.value = status;
  selectedIndex.value = 0;
  void load();
}

async function addSubscription(): Promise<void> {
  if (!value.value.trim()) return;
  try {
    await createSubscription({
      kind: kind.value,
      value: value.value.trim(),
      source: source.value,
    });
    value.value = "";
    await load();
    ElMessage.success("已添加订阅");
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "添加订阅失败";
  }
}

async function removeSubscription(subscription: SubscriptionSummary): Promise<void> {
  try {
    await deleteSubscription(subscription.id);
    await load();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "删除订阅失败";
  }
}

async function refresh(): Promise<void> {
  isRefreshing.value = true;
  errorMessage.value = "";
  try {
    const result = await refreshFeed();
    await load();
    ElMessage.success("已刷新：订阅 " + result.subscriptions + " 个，抓取 " + result.items + " 条");
    if ((result.errors ?? []).length) {
      ElMessage.warning((result.errors ?? []).length + " 个订阅抓取失败");
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "刷新 Feed 失败";
  } finally {
    isRefreshing.value = false;
  }
}

async function save(item: FeedItemSummary): Promise<void> {
  try {
    const updated = await saveFeedItem(item.id);
    await load();
    ElMessage.success("已存入阅读队列");
    if (updated.paper_id) {
      emit("open", updated.paper_id);
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存失败";
  }
}

async function ignore(item: FeedItemSummary): Promise<void> {
  try {
    await ignoreFeedItem(item.id);
    await load();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "忽略失败";
  }
}

function openPaper(item: FeedItemSummary): void {
  if (item.paper_id) {
    emit("open", item.paper_id);
  }
}

function selectRow(index: number): void {
  selectedIndex.value = index;
  void nextTick(() => {
    window.document
      .querySelector(".feed-row.is-selected")
      ?.scrollIntoView({ block: "nearest" });
  });
}

function handleKeydown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (
    target &&
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
  ) {
    return;
  }
  if (event.metaKey || event.ctrlKey || event.altKey || !items.value.length) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "j" || key === "k") {
    event.preventDefault();
    const delta = key === "j" ? 1 : -1;
    selectRow(Math.max(0, Math.min(items.value.length - 1, selectedIndex.value + delta)));
    return;
  }
  if (key === "s" || key === "x") {
    const item = items.value[selectedIndex.value];
    if (!item || item.status !== "new") return;
    event.preventDefault();
    void (key === "s" ? save(item) : ignore(item));
    return;
  }
  if (event.key === "Enter") {
    const item = items.value[selectedIndex.value];
    if (!item) return;
    event.preventDefault();
    if (item.paper_id) {
      openPaper(item);
    } else if (item.status === "new") {
      void save(item);
    }
  }
}

onMounted(() => {
  void load();
  window.addEventListener("keydown", handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", handleKeydown);
});
</script>

<template>
  <section class="feed-view" aria-label="领域跟进">
    <header class="feed-view__bar">
      <div>
        <p class="feed-view__eyebrow">Feed · 未处理 {{ items.length }} 条</p>
        <h1 class="feed-view__title">领域跟进</h1>
        <p class="feed-view__subtitle">订阅关键词 / 作者 / venue，抓取新论文并存入阅读队列。</p>
      </div>
      <div class="feed-view__actions">
        <button
          type="button"
          class="feed-view__refresh"
          :disabled="isRefreshing"
          @click="refresh"
        >
          {{ isRefreshing ? "抓取中…" : "刷新 Feed" }}
        </button>
      </div>
    </header>

    <StateBlock
      v-if="errorMessage"
      kind="error"
      title="读取 Feed 失败"
      :description="errorMessage"
      action-label="重试"
      compact
      @action="load"
    />

    <div class="feed-view__grid">
      <aside class="feed-view__subscriptions">
        <header class="feed-view__section-head">
          <h2>订阅</h2>
          <span>{{ subscriptions.length }} 个</span>
        </header>

        <div class="feed-view__form">
          <div class="feed-view__form-row">
            <select v-model="source" class="feed-view__select">
              <option v-for="option in SOURCE_OPTIONS" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <select v-model="kind" class="feed-view__select">
              <option v-for="option in KIND_OPTIONS" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </div>
          <input
            v-model="value"
            class="feed-view__input"
            type="text"
            placeholder="RAG / Vaswani / NeurIPS"
            @keyup.enter="addSubscription"
          />
          <button type="button" class="feed-view__add" @click="addSubscription">添加订阅</button>
        </div>

        <StateBlock
          v-if="!subscriptions.length"
          kind="empty"
          compact
          description="还没有订阅。添加关键词或作者后刷新。"
        />
        <ul v-else class="feed-view__subs">
          <li v-for="subscription in subscriptions" :key="subscription.id">
            <span class="feed-view__sub-value">{{ subscription.value }}</span>
            <small>{{ subscription.source }} · {{ subscription.kind }}</small>
            <button
              type="button"
              class="feed-view__link"
              @click="removeSubscription(subscription)"
            >
              删除
            </button>
          </li>
        </ul>
      </aside>

      <section class="feed-view__inbox">
        <div class="feed-view__inbox-head">
          <div class="feed-view__filters" role="tablist" aria-label="Feed 状态">
            <button
              v-for="option in STATUS_OPTIONS"
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
            @dblclick="item.paper_id ? openPaper(item) : save(item)"
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
              <button
                v-if="item.status === 'new'"
                type="button"
                @click.stop="save(item)"
              >
                保存
              </button>
              <button
                v-if="item.status === 'new'"
                type="button"
                @click.stop="ignore(item)"
              >
                忽略
              </button>
              <button
                v-if="item.paper_id"
                type="button"
                @click.stop="openPaper(item)"
              >
                打开
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.feed-view {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  padding: 26px 30px 40px;
  overflow-y: auto;
  background: var(--color-page);
}

.feed-view__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.feed-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.feed-view__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
}

.feed-view__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.feed-view__refresh {
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-accent);
  padding: 8px 14px;
  color: var(--color-white);
  font-size: 12px;
}

.feed-view__refresh:disabled {
  opacity: 0.6;
}

.feed-view__grid {
  display: grid;
  grid-template-columns: minmax(220px, 260px) minmax(0, 1fr);
  gap: 30px;
}

.feed-view__section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.feed-view__section-head h2 {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
}

.feed-view__section-head span {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.feed-view__form {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-bottom: 14px;
}

.feed-view__form-row {
  display: flex;
  gap: 6px;
}

.feed-view__input,
.feed-view__select {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 8px;
  color: var(--color-text);
  font: inherit;
  font-size: 11px;
}

.feed-view__form-row .feed-view__select {
  flex: 1;
}

.feed-view__add {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 6px 10px;
  color: var(--color-text-soft);
  font-size: 11px;
}

.feed-view__add:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.feed-view__subs {
  margin: 0;
  padding: 0;
  list-style: none;
}

.feed-view__subs li {
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--color-border);
  padding: 8px 0;
  font-size: 11px;
}

.feed-view__sub-value {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  color: var(--color-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-view__subs small {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 9px;
}

.feed-view__link {
  border: 0;
  background: transparent;
  padding: 0;
  color: var(--color-text-muted);
  font-size: 10px;
}

.feed-view__link:hover {
  color: var(--color-accent);
}

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
  border-bottom-color: var(--color-accent);
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
  color: var(--color-accent);
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
  color: var(--color-accent);
  font-size: 10px;
}

.feed-view__empty,
.feed-view__error {
  padding: 24px 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.feed-view__error {
  padding: 0;
  color: var(--color-danger);
}

@media (max-width: 1000px) {
  .feed-view__grid {
    grid-template-columns: 1fr;
  }
}
</style>
