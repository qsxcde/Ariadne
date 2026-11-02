import { describe, expect, it } from "vitest";
import { findBlockBySection, normalizeSection } from "../section";
import type { PaperBlock } from "../../api";

function block(id: string, path: string[], page = 1): PaperBlock {
  return { id, type: "paragraph", text: "", section_path: path, page_number: page };
}

const BLOCKS: PaperBlock[] = [
  block("b1", ["3 Method", "3.2 Encoder"], 2),
  block("b2", ["4 Experiments"], 5),
];

describe("findBlockBySection", () => {
  it("trims and lowercases section titles", () => {
    expect(normalizeSection("  3.2   Encoder ")).toBe("3.2 encoder");
  });

  it("matches the last segment of section_path", () => {
    expect(findBlockBySection(BLOCKS, " 3.2 ENCODER ")?.id).toBe("b1");
  });

  it("falls back to a path substring match", () => {
    expect(findBlockBySection(BLOCKS, "Experiments")?.id).toBe("b2");
  });

  it("returns null for empty or unknown titles", () => {
    expect(findBlockBySection(BLOCKS, "  ")).toBeNull();
    expect(findBlockBySection(BLOCKS, "Conclusion")).toBeNull();
    expect(findBlockBySection([], "Method")).toBeNull();
  });
});
