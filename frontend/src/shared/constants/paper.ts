/** 论文阅读状态：值与后端 `reading_status` 一致，文案全前端唯一来源。 */

export const PAPER_STATUS_OPTIONS = [
  { value: "inbox", label: "待读" },
  { value: "queued", label: "队列中" },
  { value: "skimming", label: "速读" },
  { value: "reading", label: "在读" },
  { value: "read", label: "已读" },
  { value: "archived", label: "已归档" },
] as const;

/** 文献库筛选用：首项为「全部」，值为空字符串。 */
export const PAPER_STATUS_FILTER_OPTIONS = [
  { value: "", label: "全部" },
  ...PAPER_STATUS_OPTIONS,
];

const PAPER_STATUS_LABELS: Record<string, string> = Object.fromEntries(
  PAPER_STATUS_OPTIONS.map((option) => [option.value, option.label]),
);

export function paperStatusLabel(status: string): string {
  return PAPER_STATUS_LABELS[status] ?? status;
}
