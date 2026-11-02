<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
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
  library: [];
  open: [paperId: string];
}>();

const subscriptions = ref<SubscriptionSummary[]>([]);
const items = ref<FeedItemSummary[]>([]);
const kind = ref<SubscriptionCreatePayload["kind"]>("keyword");
const source = ref<SubscriptionCreatePayload["source"]>("arxiv");
const value = ref("");
const statusFilter = ref("new");
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
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取 Feed 失败";
  } finally {
    isLoading.value = false;
  }
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

onMounted(() => {
  void load();
});
</script>

<template>
  <section class="feed-view" aria-label="领域跟进">
    <header class="feed-view__bar">
      <div>
        <p class="feed-view__eyebrow">Feed</p>
        <h1 class="feed-view__title">领域跟进</h1>
        <p class="feed-view__subtitle">订阅关键词/作者/venue，抓取新论文并存入阅读队列。</p>
      </div>
      <div class="feed-view__actions">
        <button type="button" class="feed-view__button" @click="emit('library')">文献库</button>
        <button
          type="button"
          class="feed-view__button feed-view__button--primary"
          :disabled="isRefreshing"
          @click="refresh"
        >
          {{ isRefreshing ? "抓取中…" : "刷新 Feed" }}
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="feed-view__error">{{ errorMessage }}</p>

    <div class="feed-view__grid">
      <aside class="feed-view__panel">
        <header class="feed-view__panel-head">
          <h2>订阅</h2>
          <span>{{ subscriptions.length }} 个</span>
        </header>
        <div class="feed-view__form">
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
          <input
            v-model="value"
            class="feed-view__input"
            type="text"
            placeholder="例如 RAG / Vaswani / NeurIPS"
            @keyup.enter="addSubscription"
          />
          <button type="button" class="feed-view__button feed-view__button--primary" @click="addSubscription">
            添加
          </button>
        </div>
        <p v-if="!subscriptions.length" class="feed-view__empty">还没有订阅。</p>
        <ul v-else class="feed-view__subs">
          <li v-for="subscription in subscriptions" :key="subscription.id">
            <span>{{ subscription.value }}</span>
            <small>{{ subscription.source }} · {{ subscription.kind }}</small>
            <button type="button" class="feed-view__link" @click="removeSubscription(subscription)">
              删除
            </button>
          </li>
        </ul>
      </aside>

      <section class="feed-view__panel feed-view__panel--wide">
        <header class="feed-view__panel-head">
          <h2>新论文</h2>
          <select v-model="statusFilter" class="feed-view__select" @change="load">
            <option value="new">未处理</option>
            <option value="saved">已保存</option>
            <option value="ignored">已忽略</option>
            <option value="">全部</option>
          </select>
        </header>

        <p v-if="isLoading" class="feed-view__empty">正在读取 Feed…</p>
        <p v-else-if="!items.length" class="feed-view__empty">
          没有内容。添加订阅后点「刷新 Feed」。
        </p>
        <div v-else class="feed-view__list">
          <article v-for="item in items" :key="item.id" class="feed-card">
            <header class="feed-card__head">
              <span class="feed-card__source">{{ item.source }}</span>
              <span class="feed-card__date">{{ item.published_at?.slice(0, 10) }}</span>
            </header>
            <h3 class="feed-card__title">{{ item.title }}</h3>
            <p class="feed-card__authors">{{ (item.authors ?? []).join("、") }}</p>
            <p class="feed-card__reason">{{ item.relevance_reason }}</p>
            <p v-if="item.abstract" class="feed-card__abstract">{{ item.abstract }}</p>
            <div class="feed-card__actions">
              <button
                v-if="item.status === 'new'"
                type="button"
                class="feed-view__button feed-view__button--primary"
                @click="save(item)"
              >
                存入队列
              </button>
              <button
                v-if="item.status === 'new'"
                type="button"
                class="feed-view__button"
                @click="ignore(item)"
              >
                忽略
              </button>
              <button
                v-if="item.paper_id"
                type="button"
                class="feed-view__link"
                @click="openPaper(item)"
              >
                打开论文
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
  padding: 28px 34px;
  overflow-y: auto;
  background: var(--color-bg);
}

.feed-view__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.feed-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.feed-view__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
}

.feed-view__subtitle {
  margin: 8px 0 0;
  color: var(--color-text-muted);
  font-size: 13px;
}

.feed-view__actions {
  display: flex;
  gap: 8px;
}

.feed-view__button,
.feed-view__link {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-panel);
  color: var(--color-text);
  cursor: pointer;
  font-size: 12px;
  padding: 7px 10px;
}

.feed-view__button--primary {
  border-color: var(--color-accent);
  background: var(--color-accent);
  color: #fff;
}

.feed-view__button:disabled {
  cursor: wait;
  opacity: 0.6;
}

.feed-view__link {
  border: 0;
  background: transparent;
  color: var(--color-accent);
  padding: 0;
}

.feed-view__grid {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(0, 2fr);
  gap: 14px;
}

.feed-view__panel {
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  background: var(--color-panel);
}

.feed-view__panel--wide {
  min-width: 0;
}

.feed-view__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  color: var(--color-text-muted);
  font-size: 12px;
}

.feed-view__panel-head h2 {
  margin: 0;
  color: var(--color-text);
  font-size: 15px;
}

.feed-view__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.feed-view__input,
.feed-view__select {
  border: 1px solid var(--color-border);
  border-radius: 7px;
  background: var(--color-bg);
  color: var(--color-text);
  font: inherit;
  font-size: 12px;
  padding: 7px 9px;
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
  padding: 7px 0;
  border-bottom: 1px solid var(--color-border);
  font-size: 12px;
}

.feed-view__subs span {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feed-view__subs small {
  color: var(--color-text-muted);
}

.feed-view__empty {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.feed-view__error {
  margin: 0;
  color: var(--color-danger);
  font-size: 12px;
}

.feed-view__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feed-card {
  padding: 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
}

.feed-card__head {
  display: flex;
  justify-content: space-between;
  color: var(--color-text-muted);
  font-size: 10px;
  text-transform: uppercase;
}

.feed-card__title {
  margin: 6px 0 4px;
  font-size: 14px;
}

.feed-card__authors,
.feed-card__reason,
.feed-card__abstract {
  margin: 0 0 5px;
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.feed-card__reason {
  color: var(--color-accent);
}

.feed-card__abstract {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.feed-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .feed-view__grid {
    grid-template-columns: 1fr;
  }
}
</style>
