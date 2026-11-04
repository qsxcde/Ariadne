/** 触发浏览器下载一段文本，避免各页面重复拼 Blob 与临时链接。 */
export function downloadText(
  content: string,
  filename: string,
  type = "text/plain;charset=utf-8",
): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
