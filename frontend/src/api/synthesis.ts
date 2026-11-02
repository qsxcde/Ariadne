import { jsonRequest, requestJson } from "./client";
import type { CollectionAskResult, PaperComparison } from "./types";

export function askCollection(
  collectionId: string,
  question: string,
): Promise<CollectionAskResult> {
  return requestJson<CollectionAskResult>(
    `/collections/${collectionId}/ask`,
    "集合问答失败",
    { method: "POST", ...jsonRequest({ question }) },
  );
}

export function compareCollectionPapers(
  collectionId: string,
  paperIds: string[],
): Promise<PaperComparison[]> {
  return requestJson<PaperComparison[]>(
    `/collections/${collectionId}/compare`,
    "论文对比失败",
    { method: "POST", ...jsonRequest({ paper_ids: paperIds }) },
  );
}
