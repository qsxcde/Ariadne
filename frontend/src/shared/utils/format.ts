import { BYTES_PER_MB } from "@/shared/constants/app";

/**
 * 文件大小展示：统一保留两位小数并补 MB 单位。
 * 后端要求至少 0.01MB，避免 0.00MB 让用户误以为文件为空。
 */
export function formatFileSize(bytes: number, prefix = ""): string {
  const megabytes = Math.max(bytes / BYTES_PER_MB, 0.01);
  return `${prefix}${megabytes.toFixed(2)}MB`;
}

/** 时间戳展示：`10-25 14:03`，解析失败时回落原文。 */
export function formatUpdatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

/** 阅读时长展示：不足 1 分钟按 1 分钟，超过 1 小时拆成小时与分钟。 */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.max(0, Math.round(seconds / 60));
  if (totalMinutes < 60) {
    return `${totalMinutes} 分钟`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? `${hours} 小时 ${minutes} 分` : `${hours} 小时`;
}

/** 页码展示：单页 `p.4`，跨页 `p.4-5`，缺省返回空串。 */
export function formatPageRange(start?: number | null, end?: number | null): string {
  if (start == null && end == null) {
    return "";
  }
  if (start == null) {
    return `p.${end}`;
  }
  if (end == null || end === start) {
    return `p.${start}`;
  }
  return `p.${start}-${end}`;
}
