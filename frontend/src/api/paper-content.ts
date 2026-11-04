import { fetchBinary, requestJson } from "@/api/client";
import type { PaperContent } from "@/api/types";

/** 读取解析后的结构化正文，用于阅读器渲染与引用定位。 */
export function getPaperContent(sessionId: string, documentId: string): Promise<PaperContent> {
  return requestJson<PaperContent>(
    `/sessions/${sessionId}/documents/${documentId}/content`,
    "读取正文失败",
  );
}

/** 按正文块 bbox 从原始 PDF 裁切图片，公式/插图展示用。 */
export async function fetchBlockCrop(
  sessionId: string,
  documentId: string,
  blockId: string,
  scale = 2,
): Promise<Blob> {
  const buffer = await fetchBinary(
    `/sessions/${sessionId}/documents/${documentId}/blocks/${encodeURIComponent(blockId)}/crop?scale=${scale}`,
    "读取原图失败",
  );
  return new Blob([buffer], { type: "image/png" });
}
