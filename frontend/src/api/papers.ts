import { jsonRequest, requestForm, requestJson } from "./client";
import type { PaperDetail, PaperSummary, PaperUpdatePayload, PaperUploadResult } from "./types";

export type PaperListFilters = {
  status?: string;
  collectionId?: string;
  tag?: string;
  query?: string;
  limit?: number;
};

function buildQuery(filters: PaperListFilters): string {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.collectionId) params.set("collection_id", filters.collectionId);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.query) params.set("q", filters.query);
  if (filters.limit) params.set("limit", String(filters.limit));
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listPapers(filters: PaperListFilters = {}): Promise<PaperSummary[]> {
  return requestJson<PaperSummary[]>(
    `/papers${buildQuery(filters)}`,
    "读取文献库失败",
  );
}

export function getPaper(paperId: string): Promise<PaperDetail> {
  return requestJson<PaperDetail>(`/papers/${paperId}`, "读取论文失败");
}

export function uploadPaper(file: File): Promise<PaperUploadResult> {
  const body = new FormData();
  body.append("file", file);
  return requestForm<PaperUploadResult>("/papers", "上传论文失败", body);
}

export function updatePaper(
  paperId: string,
  payload: PaperUpdatePayload,
): Promise<PaperDetail> {
  return requestJson<PaperDetail>(`/papers/${paperId}`, "更新论文失败", {
    method: "PATCH",
    ...jsonRequest(payload),
  });
}
