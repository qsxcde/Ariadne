import { nextTick, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  createSubscription,
  deleteSubscription,
  ignoreFeedItem,
  listFeed,
  listSubscriptions,
  refreshFeed,
  saveFeedItem,
} from "@/api/feed";
import type { FeedItemSummary, SubscriptionCreatePayload, SubscriptionSummary } from "@/api";

export const KIND_OPTIONS = [
  { value: "keyword", label: "关键词" },
  { value: "author", label: "作者" },
  { value: "venue", label: "会议/期刊" },
  { value: "institution", label: "机构" },
];

export const SOURCE_OPTIONS = [
  { value: "arxiv", label: "arXiv" },
  { value: "openalex", label: "OpenAlex" },
  { value: "pubmed", label: "PubMed" },
  { value: "rss", label: "RSS" },
];

export const FEED_STATUS_OPTIONS = [
  { value: "new", label: "未处理" },
  { value: "saved", label: "已保存" },
  { value: "ignored", label: "已忽略" },
  { value: "", label: "全部" },
];

const KIND_LABELS = Object.fromEntries(KIND_OPTIONS.map((option) => [option.value, option.label]));
const SOURCE_LABELS = Object.fromEntries(
  SOURCE_OPTIONS.map((option) => [option.value, option.label]),
);

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

function kindLabel(value: string): string {
  return KIND_LABELS[value] ?? value;
}

function sourceLabel(value: string): string {
  return SOURCE_LABELS[value] ?? value;
}

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

/** 保存到阅读队列，返回可直接打开的 paper id。 */
async function save(item: FeedItemSummary): Promise<string | null> {
  try {
    const updated = await saveFeedItem(item.id);
    await load();
    ElMessage.success("已存入阅读队列");
    return updated.paper_id ?? null;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存失败";
    return null;
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

function selectRow(index: number): void {
  selectedIndex.value = index;
  void nextTick(() => {
    window.document
      .querySelector(".feed-row.is-selected")
      ?.scrollIntoView({ block: "nearest" });
  });
}

export function useFeed() {
  return {
    subscriptions,
    items,
    kind,
    source,
    value,
    statusFilter,
    selectedIndex,
    isLoading,
    isRefreshing,
    errorMessage,
    kindLabel,
    sourceLabel,
    load,
    selectStatus,
    addSubscription,
    removeSubscription,
    refresh,
    save,
    ignore,
    selectRow,
  };
}
