import { jsonRequest, requestForm, requestJson, requestText, requestVoid } from "./client";
import type {
  ExplainResponse,
  CitationGraph,
  GlossaryResponse,
  LibraryStats,
  PaperBrief,
  PaperDetail,
  PaperSummary,
  PaperImportPayload,
  PaperImportResult,
  PaperUpdatePayload,
  PaperUploadResult,
  WeeklyReview,
} from "./types";

type PaperListFilters = {
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

export function importPaperByReference(
  payload: PaperImportPayload,
): Promise<PaperImportResult> {
  return requestJson<PaperImportResult>("/papers/import", "导入论文失败", {
    method: "POST",
    ...jsonRequest(payload),
  });
}

export function recordReadingTime(
  paperId: string,
  seconds: number,
): Promise<{ paper_id: string; added_seconds: number; total_seconds: number }> {
  return requestJson(`/papers/${paperId}/reading-time`, "记录阅读时长失败", {
    method: "POST",
    ...jsonRequest({ seconds }),
  });
}

export function getCitations(paperId: string): Promise<CitationGraph> {
  return requestJson<CitationGraph>(`/papers/${paperId}/citations`, "读取引用关系失败");
}

export function getGlossary(paperId: string): Promise<GlossaryResponse> {
  return requestJson<GlossaryResponse>(`/papers/${paperId}/glossary`, "生成术语表失败");
}

export function getLibraryStats(): Promise<LibraryStats> {
  return requestJson<LibraryStats>("/papers/stats", "读取统计失败");
}

export function exportBibtex(): Promise<string> {
  return requestText("/papers/export.bib", "导出 BibTeX 失败");
}

export function saveWeeklyNote(note: string): Promise<WeeklyReview> {
  return requestJson<WeeklyReview>("/review/weekly/note", "保存复盘失败", {
    method: "PUT",
    ...jsonRequest({ note }),
  });
}

export function getWeeklyReview(): Promise<WeeklyReview> {
  return requestJson<WeeklyReview>("/review/weekly", "读取周报失败");
}

export function getPaperBrief(
  paperId: string,
  force = false,
): Promise<PaperBrief> {
  const query = force ? "?force=true" : "";
  return requestJson<PaperBrief>(`/papers/${paperId}/brief${query}`, "生成速读卡失败", {
    method: "POST",
  });
}

export function explainSelection(
  paperId: string,
  text: string,
  mode: "explain" | "translate" | "simplify",
): Promise<ExplainResponse> {
  return requestJson<ExplainResponse>(
    `/papers/${paperId}/explain`,
    "解释失败",
    { method: "POST", ...jsonRequest({ text, mode }) },
  );
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

export function deletePaper(paperId: string): Promise<void> {
  return requestVoid(`/papers/${paperId}`, "删除论文失败", { method: "DELETE" });
}
