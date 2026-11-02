import { jsonRequest, requestJson, requestVoid } from "./client";
import type {
  FeedItemSummary,
  FeedRefreshResult,
  SubscriptionCreatePayload,
  SubscriptionSummary,
} from "./types";

export function listSubscriptions(): Promise<SubscriptionSummary[]> {
  return requestJson<SubscriptionSummary[]>("/subscriptions", "读取订阅失败");
}

export function createSubscription(
  payload: SubscriptionCreatePayload,
): Promise<SubscriptionSummary> {
  return requestJson<SubscriptionSummary>("/subscriptions", "创建订阅失败", {
    method: "POST",
    ...jsonRequest(payload),
  });
}

export function deleteSubscription(subscriptionId: string): Promise<void> {
  return requestVoid("/subscriptions/" + subscriptionId, "删除订阅失败", {
    method: "DELETE",
  });
}

export function listFeed(status?: string): Promise<FeedItemSummary[]> {
  const query = status ? "?status=" + encodeURIComponent(status) : "";
  return requestJson<FeedItemSummary[]>("/feed" + query, "读取 Feed 失败");
}

export function refreshFeed(): Promise<FeedRefreshResult> {
  return requestJson<FeedRefreshResult>("/feed/refresh", "刷新 Feed 失败", {
    method: "POST",
  });
}

export function saveFeedItem(itemId: string): Promise<FeedItemSummary> {
  return requestJson<FeedItemSummary>("/feed/" + itemId + "/save", "保存论文失败", {
    method: "POST",
  });
}

export function ignoreFeedItem(itemId: string): Promise<FeedItemSummary> {
  return requestJson<FeedItemSummary>("/feed/" + itemId + "/ignore", "忽略失败", {
    method: "POST",
  });
}
