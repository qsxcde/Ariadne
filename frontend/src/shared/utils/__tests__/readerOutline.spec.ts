import { describe, expect, it } from "vitest";

import type { PaperBlock } from "@/api";
import { buildReaderOutline } from "@/shared/utils/readerOutline";

function block(overrides: Partial<PaperBlock>): PaperBlock {
  return {
    id: "b-0",
    type: "paragraph",
    text: "",
    section_path: ["Abstract"],
    page_number: 1,
    has_image: false,
    ...overrides,
  };
}

describe("buildReaderOutline", () => {
  it("按 section_path 变化生成目录，标题用块自身文本", () => {
    const items = buildReaderOutline([
      block({ id: "b0", type: "title", text: "1 Introduction", section_path: ["Introduction"] }),
      block({ id: "b1", text: "body", section_path: ["Introduction"] }),
      block({ id: "b2", type: "title", text: "2 Method", section_path: ["Method"] }),
      block({ id: "b3", text: "body", section_path: ["Method"] }),
    ]);

    expect(items.map((item) => item.title)).toEqual(["1 Introduction", "2 Method"]);
    expect(items.map((item) => item.blockId)).toEqual(["b0", "b2"]);
    expect(items[0].key).toBe("section-Introduction");
  });

  it("老产物 section_path 不变化时退回标题块", () => {
    const items = buildReaderOutline([
      block({ id: "b0", type: "title", text: "A Fuzzy MIL Framework" }),
      block({ id: "b1", text: "body" }),
      block({ id: "b2", type: "title", text: "I. INTRODUCTION" }),
    ]);

    expect(items.map((item) => item.title)).toEqual(["A Fuzzy MIL Framework", "I. INTRODUCTION"]);
    expect(items[1].key).toBe("block-b2");
  });

  it("层级按 section_path 深度递增", () => {
    const items = buildReaderOutline([
      block({ id: "b0", type: "title", text: "Intro", section_path: ["Intro"] }),
      block({ id: "b1", type: "title", text: "Sub", section_path: ["Intro", "Sub"] }),
    ]);

    expect(items.map((item) => item.level)).toEqual([2, 3]);
  });

  it("纯文本解析没有标题时只保留首个锚点", () => {
    const items = buildReaderOutline([
      block({ id: "b0", text: "Prepared for submission to JCAP" }),
      block({ id: "b1", text: "More body text" }),
    ]);

    expect(items).toHaveLength(1);
    expect(items[0].title).toBe("Abstract");
    expect(items[0].blockId).toBe("b0");
  });

  it("连续同名标题不重复进目录", () => {
    const items = buildReaderOutline([
      block({ id: "b0", type: "title", text: "References", section_path: ["References"] }),
      block({ id: "b1", type: "title", text: "References", section_path: ["References"] }),
    ]);

    expect(items).toHaveLength(1);
  });
});
