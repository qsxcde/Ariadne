import { jsonRequest, requestJson, requestVoid } from "@/api/client";
import type { AnnotationCreatePayload, AnnotationSummary } from "@/api/types";

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

export function deleteAnnotation(annotationId: string): Promise<void> {
  return requestVoid(`/annotations/${annotationId}`, "删除笔记失败", {
    method: "DELETE",
  });
}
