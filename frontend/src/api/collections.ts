import { jsonRequest, requestJson, requestVoid } from "./client";
import type { CollectionCreatePayload, CollectionSummary } from "./types";

export function listCollections(): Promise<CollectionSummary[]> {
  return requestJson<CollectionSummary[]>("/collections", "读取集合失败");
}

export function createCollection(
  payload: CollectionCreatePayload,
): Promise<CollectionSummary> {
  return requestJson<CollectionSummary>("/collections", "创建集合失败", {
    method: "POST",
    ...jsonRequest(payload),
  });
}

export function addPaperToCollection(
  collectionId: string,
  paperId: string,
): Promise<void> {
  return requestVoid(
    `/collections/${collectionId}/papers/${paperId}`,
    "加入集合失败",
    { method: "PUT" },
  );
}

export function removePaperFromCollection(
  collectionId: string,
  paperId: string,
): Promise<void> {
  return requestVoid(
    `/collections/${collectionId}/papers/${paperId}`,
    "移出集合失败",
    { method: "DELETE" },
  );
}
