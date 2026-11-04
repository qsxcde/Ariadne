export type CopyResult = "ok" | "unsupported" | "failed";

/** 复制文本：区分「环境不支持」与「写入失败」，供调用方给出不同提示。 */
export async function copyText(text: string): Promise<CopyResult> {
  if (!text) {
    return "failed";
  }
  if (!navigator.clipboard?.writeText) {
    return "unsupported";
  }
  try {
    await navigator.clipboard.writeText(text);
    return "ok";
  } catch {
    return "failed";
  }
}
