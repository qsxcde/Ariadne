import { jsonRequest, requestJson, requestVoid } from "@/api/client";
import type {
  DocumentUploadResult,
  IndexRebuildResult,
  SessionSnapshot,
  SessionSummary,
  SessionUpdatePayload,
} from "@/api/types";

export async function createSession(): Promise<string> {
  const data = await requestJson<{ session_id: string }>("/sessions", "创建会话失败", {
    method: "POST",
  });
  return data.session_id;
}

export function listSessions(): Promise<SessionSummary[]> {
  return requestJson<SessionSummary[]>("/sessions", "读取会话列表失败");
}

export function getSession(sessionId: string): Promise<SessionSnapshot> {
  return requestJson<SessionSnapshot>(`/sessions/${sessionId}`, "读取会话详情失败");
}

export function rebuildSessionIndex(sessionId: string): Promise<IndexRebuildResult> {
  return requestJson<IndexRebuildResult>(
    `/sessions/${sessionId}/index/rebuild`,
    "重建索引失败",
    { method: "POST" },
  );
}

export function updateSession(
  sessionId: string,
  payload: SessionUpdatePayload,
): Promise<SessionSummary> {
  return requestJson<SessionSummary>(`/sessions/${sessionId}`, "更新会话失败", {
    method: "PATCH",
    ...jsonRequest(payload),
  });
}

export function archiveSession(sessionId: string): Promise<void> {
  return requestVoid(`/sessions/${sessionId}`, "归档会话失败", { method: "DELETE" });
}

export function uploadDocument(sessionId: string, file: File): Promise<DocumentUploadResult> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<DocumentUploadResult>(`/sessions/${sessionId}/documents`, "上传论文失败", {
    method: "POST",
    body: form,
  });
}
