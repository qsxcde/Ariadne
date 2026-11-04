import type { SelectionAskMode } from "@/shared/types";

const MAX_QUOTE_CHARS = 400;

/**
 * 把阅读器里的选区转成一条可直接发送的提问。
 * 引用块用 Markdown 引用语法，模型能明确区分「用户问题」与「论文原文」。
 */
export function buildSelectionPrompt(text: string, mode: SelectionAskMode): string {
  const quote = text.trim().replace(/\s+/g, " ").slice(0, MAX_QUOTE_CHARS);
  if (mode === "explain") {
    return `请解释这段原文，并结合论文上下文说明它的作用：\n\n> ${quote}`;
  }
  if (mode === "translate") {
    return `请把这段原文翻译成中文，保留术语、公式和数字：\n\n> ${quote}`;
  }
  if (mode === "simplify") {
    return `请用更简单的中文重述这段原文，保留技术含义：\n\n> ${quote}`;
  }
  return `围绕这段原文继续追问：\n\n> ${quote}\n\n`;
}
