import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api", () => ({
  streamChat: vi.fn(),
  fetchAgentRun: vi.fn(),
}));

import { fetchAgentRun, streamChat } from "@/api";
import type { AgentRunDetail, MessageChunk } from "@/api";
import {
  isAgentRunActive,
  resetAgentRuns,
  useAgentRuns,
} from "@/features/agent/composables/useAgentRuns";

function streamOf(chunks: MessageChunk[]) {
  return (async function* () {
    for (const chunk of chunks) {
      yield chunk;
    }
  })();
}

beforeEach(() => {
  vi.mocked(streamChat).mockReset();
  vi.mocked(fetchAgentRun).mockReset();
  resetAgentRuns();
});

describe("useAgentRuns", () => {
  it("归并工具步骤、答案与来源", async () => {
    vi.mocked(streamChat).mockReturnValue(
      streamOf([
        { type: "run_started", value: { run_id: "run-1", max_steps: 6 } },
        { type: "status", value: "tool_running" },
        {
          type: "tool_call",
          value: { run_id: "run-1", step: 1, tool: "search_session_chunks", arguments: { query: "attention" } },
        },
        {
          type: "tool_result",
          value: {
            run_id: "run-1",
            step: 1,
            tool: "search_session_chunks",
            status: "ok",
            summary: "命中 2 个片段",
            sources: [{ section: "Introduction", chunk_index: 0 }],
          },
        },
        { type: "status", value: "answering" },
        { type: "token", value: "答" },
        { type: "token", value: "案" },
        { type: "sources", value: [{ section: "Introduction", chunk_index: 0 }] },
        { type: "done", run_id: "run-1" },
      ]),
    );

    const { startRun } = useAgentRuns();
    const run = startRun({ sessionId: "s1", goal: "attention?", paperId: "p1" });
    expect(run).not.toBeNull();
    expect(run?.status).toBe("planning");

    await vi.waitFor(() => expect(run?.status).toBe("completed"));

    expect(run?.id).toBe("run-1");
    expect(run?.steps).toHaveLength(1);
    expect(run?.steps[0]).toMatchObject({
      step: 1,
      tool: "search_session_chunks",
      status: "ok",
      summary: "命中 2 个片段",
    });
    expect(run?.answer).toBe("答案");
    expect(run?.sources[0].section).toBe("Introduction");
  });

  it("停止后保留已生成答案且不被 done 覆盖", async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.mocked(streamChat).mockReturnValue(
      (async function* () {
        yield { type: "run_started", value: { run_id: "run-stop", max_steps: 6 } } as MessageChunk;
        yield { type: "token", value: "half" } as MessageChunk;
        await gate;
        yield { type: "done", run_id: "run-stop" } as MessageChunk;
      })(),
    );

    const { startRun, stopRun } = useAgentRuns();
    const run = startRun({ sessionId: "s1", goal: "q" });
    await vi.waitFor(() => expect(run?.answer).toBe("half"));

    stopRun(run?.localId);
    expect(run?.status).toBe("stopped");

    release();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(run?.status).toBe("stopped");
    expect(run?.answer).toBe("half");
  });

  it("传输失败标记为 failed 并保留错误信息", async () => {
    vi.mocked(streamChat).mockImplementation(() => {
      throw new Error("network down");
    });

    const { startRun } = useAgentRuns();
    const run = startRun({ sessionId: "s1", goal: "q" });

    await vi.waitFor(() => expect(run?.status).toBe("failed"));
    expect(run?.error).toBe("network down");
    expect(isAgentRunActive(run!.status)).toBe(false);
  });

  it("按 run_id 回放历史轨迹", async () => {
    vi.mocked(fetchAgentRun).mockResolvedValue({
      id: "run-history",
      session_id: "s1",
      status: "completed",
      max_steps: 6,
      step_count: 1,
      created_at: "2026-11-04T10:00:00+00:00",
      finished_at: "2026-11-04T10:00:10+00:00",
      question: "历史问题",
      answer: "历史答案",
      sources: [{ section: "Method", chunk_index: 2 }],
      steps: [
        {
          id: "step-1",
          run_id: "run-history",
          step_index: 1,
          kind: "tool",
          tool_name: "read_chunk",
          arguments: { section: "Method", chunk_index: 2 },
          sources: [{ section: "Method", chunk_index: 2 }],
          summary: "已读取 100 字",
          status: "ok",
          created_at: "2026-11-04T10:00:01+00:00",
          latency_ms: 1200,
        },
      ],
    } as AgentRunDetail);

    const { loadRun, runs, activeLocalId } = useAgentRuns();
    const loaded = await loadRun("s1", "run-history");

    expect(loaded?.goal).toBe("历史问题");
    expect(loaded?.answer).toBe("历史答案");
    expect(loaded?.steps[0].tool).toBe("read_chunk");
    expect(runs.value).toHaveLength(1);
    expect(activeLocalId.value).toBe("run-history");
  });
});
