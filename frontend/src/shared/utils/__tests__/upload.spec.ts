import { describe, expect, it } from "vitest";

import { canOpenDocument, uploadStepFromStatus } from "@/shared/utils/upload";

describe("uploadStepFromStatus", () => {
  it("按处理阶段递增进度", () => {
    const steps = ["uploaded", "parsing", "parsed", "chunked", "indexing", "ready"].map((status) =>
      uploadStepFromStatus(status),
    );
    const progresses = steps.map((step) => step.progress);

    expect(progresses).toEqual([...progresses].sort((a, b) => a - b));
    expect(steps.at(-1)).toMatchObject({ phase: "ready", progress: 100, canOpen: true });
  });

  it("解析阶段不允许打开阅读器", () => {
    for (const status of ["uploaded", "parsing", "parsed", "chunked", "indexing"]) {
      expect(canOpenDocument(status)).toBe(false);
    }
  });

  it("就绪才允许打开", () => {
    expect(canOpenDocument("ready")).toBe(true);
    expect(canOpenDocument("failed")).toBe(false);
    expect(canOpenDocument(null)).toBe(false);
  });

  it("未知状态按解析中处理", () => {
    expect(uploadStepFromStatus("some_new_stage")).toMatchObject({
      phase: "parsing",
      canOpen: false,
    });
  });
});
