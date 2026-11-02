import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/papers", () => ({
  listPapers: vi.fn(),
  getPaper: vi.fn(),
  updatePaper: vi.fn(),
  uploadPaper: vi.fn(),
}));
vi.mock("../../api/annotations", () => ({
  createAnnotation: vi.fn(),
  deleteAnnotation: vi.fn(),
}));
vi.mock("../../api/collections", () => ({
  listCollections: vi.fn(),
}));

import { createAnnotation, deleteAnnotation } from "../../api/annotations";
import { listCollections } from "../../api/collections";
import { listPapers, updatePaper } from "../../api/papers";
import type { AnnotationSummary, PaperDetail, PaperSummary } from "../../api";
import { usePapers } from "../usePapers";

function paper(overrides: Partial<PaperSummary> = {}): PaperSummary {
  return {
    id: "paper-1",
    title: "Attention",
    authors: ["Vaswani"],
    reading_status: "inbox",
    progress: 0,
    updated_at: "2026-11-03T00:00:00+00:00",
    tags: [],
    ...overrides,
  } as PaperSummary;
}

function detail(overrides: Partial<PaperDetail> = {}): PaperDetail {
  return {
    ...paper(),
    documents: [],
    annotations: [],
    collections: [],
    ...overrides,
  } as PaperDetail;
}

beforeEach(() => {
  vi.mocked(listPapers).mockReset();
  vi.mocked(listCollections).mockReset();
  vi.mocked(updatePaper).mockReset();
  vi.mocked(createAnnotation).mockReset();
  vi.mocked(deleteAnnotation).mockReset();
  usePapers().reset();
});

describe("usePapers", () => {
  it("加载文献库并保留筛选条件", async () => {
    vi.mocked(listPapers).mockResolvedValue([paper()]);
    vi.mocked(listCollections).mockResolvedValue([]);
    const store = usePapers();
    store.filters.value.status = "reading";

    await store.loadLibrary();

    expect(listPapers).toHaveBeenCalledWith(
      expect.objectContaining({ status: "reading" }),
    );
    expect(store.papers.value).toHaveLength(1);
    expect(store.paperCount.value).toBe(1);
  });

  it("保存阅读状态时同步当前论文与列表", async () => {
    vi.mocked(listPapers).mockResolvedValue([paper()]);
    vi.mocked(listCollections).mockResolvedValue([]);
    const store = usePapers();
    await store.loadLibrary();
    vi.mocked(updatePaper).mockResolvedValue(
      detail({ reading_status: "reading", progress: 0.5 }),
    );

    await store.saveReadingState("paper-1", {
      reading_status: "reading",
      progress: 0.5,
    });

    expect(store.currentPaper.value?.progress).toBe(0.5);
    expect(store.papers.value[0].progress).toBe(0.5);
    expect(store.papers.value[0].reading_status).toBe("reading");
  });

  it("新增与删除笔记会更新当前论文", async () => {
    const annotation = {
      id: "a1",
      type: "note",
      content: "remember",
      created_at: "2026-11-03T00:00:00+00:00",
      updated_at: "2026-11-03T00:00:00+00:00",
    } as AnnotationSummary;
    vi.mocked(createAnnotation).mockResolvedValue(annotation);
    const store = usePapers();
    store.currentPaper.value = detail();

    const created = await store.addNote("paper-1", "remember");
    expect(created?.id).toBe("a1");
    expect(store.currentPaper.value?.annotations).toHaveLength(1);

    await store.removeAnnotation("a1");
    expect(deleteAnnotation).toHaveBeenCalledWith("a1");
    expect(store.currentPaper.value?.annotations).toHaveLength(0);
  });
});
