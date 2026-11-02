import { jsonRequest, requestJson, requestVoid } from "./client";
import type {
  AnnotationCreatePayload,
  AnnotationSummary,
  AnnotationUpdatePayload,
} from "./types";

export function listAnnotations(
  paperId: string,
  type?: string,
): Promise<AnnotationSummary[]> {
  const query = type ? `?type=${encodeURIComponent(type)}` : "";
  return requestJson<AnnotationSummary[]>(
    `/papers/${paperId}/annotations${query}`,
    "读取笔记失败",
  );
}

export function createAnnotation(
  paperId: string,
  payload: AnnotationCreatePayload,
): Promise<AnnotationSummary> {
  return requestJson<AnnotationSummary>(
    `/papers/${paperId}/annotations`,
    "保存笔记失败",
    { method: "POST", ...jsonRequest(payload) },
  );
}

export function updateAnnotation(
  annotationId: string,
  payload: AnnotationUpdatePayload,
): Promise<AnnotationSummary> {
  return requestJson<AnnotationSummary>(
    `/annotations/${annotationId}`,
    "更新笔记失败",
    { method: "PATCH", ...jsonRequest(payload) },
  );
}

export function deleteAnnotation(annotationId: string): Promise<void> {
  return requestVoid(`/annotations/${annotationId}`, "删除笔记失败", {
    method: "DELETE",
  });
}
