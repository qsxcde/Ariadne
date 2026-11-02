import type { PaperBlock } from "../api";

/** 统一章节标题：折叠空白并忽略大小写。 */
export function normalizeSection(value: string): string {
  return value.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * 按章节标题定位正文块。
 *
 * 速读卡的章节标题来自 chunk.metadata.section，正文块的 section_path 是层级数组；
 * 先比对末级路径，失败后按完整路径包含匹配。
 */
export function findBlockBySection(
  blocks: PaperBlock[],
  title: string,
): PaperBlock | null {
  const target = normalizeSection(title);
  if (!target || !blocks.length) {
    return null;
  }
  const exact = blocks.find(
    (block) => normalizeSection(block.section_path[block.section_path.length - 1] ?? "") === target,
  );
  return (
    exact ??
    blocks.find((block) => normalizeSection(block.section_path.join(" > ")).includes(target)) ??
    null
  );
}
