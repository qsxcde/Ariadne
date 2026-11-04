import type { UploadStatus } from "@/shared/types";

/** 上传阶段（还没拿到 document 状态时使用）。 */
export const UPLOADING_STEP: UploadStep = {
  phase: "uploading",
  progress: 5,
  stageLabel: "正在上传 PDF",
  canOpen: false,
};

export type UploadStep = Pick<UploadStatus, "phase" | "progress" | "stageLabel" | "canOpen">;

const STATUS_STEPS: Record<string, UploadStep> = {
  uploaded: { phase: "uploading", progress: 12, stageLabel: "已上传，等待解析", canOpen: false },
  parsing: { phase: "parsing", progress: 35, stageLabel: "正在解析 PDF", canOpen: false },
  parsed: { phase: "parsing", progress: 60, stageLabel: "解析完成，准备分块", canOpen: false },
  chunked: { phase: "indexing", progress: 78, stageLabel: "分块完成，准备索引", canOpen: false },
  indexing: { phase: "indexing", progress: 90, stageLabel: "正在构建检索索引", canOpen: false },
  ready: { phase: "ready", progress: 100, stageLabel: "解析完成，可以打开", canOpen: true },
  failed: { phase: "error", progress: 100, stageLabel: "处理失败", canOpen: false },
};

const UNKNOWN_STEP: UploadStep = {
  phase: "parsing",
  progress: 35,
  stageLabel: "正在处理",
  canOpen: false,
};

/** 后端 document.status → 进度条阶段；未知状态按解析中处理。 */
export function uploadStepFromStatus(status: string | null | undefined): UploadStep {
  if (!status) {
    return UNKNOWN_STEP;
  }
  return STATUS_STEPS[status] ?? UNKNOWN_STEP;
}

/** 只有就绪（或示例文档）才允许打开阅读器。 */
export function canOpenDocument(status: string | null | undefined): boolean {
  return uploadStepFromStatus(status).canOpen;
}
