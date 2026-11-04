import type { PaperBlock } from "@/api";
import type { ReaderOutlineItem } from "@/shared/types";

const HEADING_TYPES = new Set(["title", "heading"]);
const MAX_OUTLINE_LEVEL = 4;
const MAX_TITLE_LENGTH = 80;

function isHeadingBlock(block: PaperBlock): boolean {
  return HEADING_TYPES.has(block.type);
}

/**
 * 阅读器目录锚点。
 *
 * 优先使用 `section_path` 变化（后端已按标题层级展开）；老解析产物里
 * `section_path` 可能停在 "Abstract"，此时退回标题块自身的文本，保证旧数据
 * 也能显示目录。
 */
export function buildReaderOutline(blocks: PaperBlock[]): ReaderOutlineItem[] {
  const items: ReaderOutlineItem[] = [];
  let lastPath = "";

  for (const block of blocks) {
    const path = block.section_path.join(" > ");
    const heading = isHeadingBlock(block);
    const pathChanged = Boolean(path) && path !== lastPath;
    if (pathChanged) {
      lastPath = path;
    }
    if (!pathChanged && !heading) {
      continue;
    }

    // 标题块用自身文本（保留原编号）；普通块用 section_path 末级。
    const title = heading
      ? block.text.trim().slice(0, MAX_TITLE_LENGTH)
      : (block.section_path.at(-1) ?? "");
    if (!title) {
      continue;
    }

    const previous = items.at(-1);
    if (!pathChanged && previous?.title === title) {
      continue;
    }

    items.push({
      key: pathChanged ? `section-${path}` : `block-${block.id}`,
      title,
      level: Math.min((block.section_path.length || 1) + 1, MAX_OUTLINE_LEVEL),
      blockId: block.id,
      pageNumber: block.page_number,
    });
  }

  return items;
}
