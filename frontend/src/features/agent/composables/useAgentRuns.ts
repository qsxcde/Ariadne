import { computed, ref } from "vue";
import { fetchAgentRun, streamChat } from "@/api";
import type { AgentRunDetail, MessageChunk } from "@/api";
import type {
  AgentRunStatus,
  AgentRunViewModel,
  AgentStepViewModel,
} from "@/shared/types";
import { toErrorMessage } from "@/shared/utils/error";

const ACTIVE_STATUSES: AgentRunStatus[] = [
  "planning",
  "tool_running",
  "answering",
  "running",
];

export function isAgentRunActive(status: AgentRunStatus): boolean {
  return ACTIVE_STATUSES.includes(status);
}

/**
 * App-level Agent run store, keyed by the server run id once it arrives.
 *
 * Singleton on purpose: route changes unmount the paper inspector, but the
 * in-flight SSE connection and every run's ledger must survive.
 */
const runs = ref<AgentRunViewModel[]>([]);
const activeLocalId = ref<string | null>(null);
const controllers = new Map<string, AbortController>();

const currentRun = computed(
  () => runs.value.find((run) => run.localId === activeLocalId.value) ?? null,
);
const runningRun = computed(
  () => runs.value.find((run) => isAgentRunActive(run.status)) ?? null,
);

function findStep(run: AgentRunViewModel, step: number): AgentStepViewModel | undefined {
  return run.steps.find((item) => item.step === step);
}

function upsertStep(
  run: AgentRunViewModel,
  step: number,
  patch: Partial<AgentStepViewModel> & { tool: string },
): AgentStepViewModel {
  const existing = findStep(run, step);
  if (existing) {
    Object.assign(existing, patch);
    return existing;
  }
  const created: AgentStepViewModel = {
    step,
    tool: patch.tool,
    arguments: patch.arguments,
    status: patch.status ?? "running",
    summary: patch.summary,
    sources: patch.sources ?? [],
    startedAt: patch.startedAt ?? Date.now(),
    finishedAt: patch.finishedAt,
    error: patch.error,
  };
  run.steps.push(created);
  return created;
}

function applyEvent(run: AgentRunViewModel, event: MessageChunk): void {
  switch (event.type) {
    case "run_started":
      run.id = event.value.run_id;
      run.maxSteps = event.value.max_steps;
      break;
    case "status":
      if (
        event.value === "planning" ||
        event.value === "tool_running" ||
        event.value === "answering"
      ) {
        if (isAgentRunActive(run.status)) {
          run.status = event.value;
        }
      }
      break;
    case "tool_call":
      upsertStep(run, event.value.step, {
        tool: event.value.tool,
        arguments: event.value.arguments ?? {},
        status: "running",
        startedAt: Date.now(),
      });
      break;
    case "tool_result": {
      const step = upsertStep(run, event.value.step, {
        tool: event.value.tool,
        status: event.value.status,
        summary: event.value.summary,
        sources: event.value.sources ?? [],
        finishedAt: Date.now(),
      });
      if (event.value.status === "error") {
        step.error = event.value.summary;
      }
      break;
    }
    case "token":
      run.answer += event.value;
      break;
    case "sources":
      run.sources = event.value;
      break;
    case "warning":
      run.warning = event.value;
      break;
    case "error":
      run.status = "failed";
      run.error = event.value;
      run.finishedAt = Date.now();
      break;
    case "done":
      if (event.run_id && !run.id) {
        run.id = event.run_id;
      }
      if (isAgentRunActive(run.status)) {
        run.status = "completed";
      }
      run.finishedAt = Date.now();
      break;
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function consume(
  run: AgentRunViewModel,
  sessionId: string,
  signal: AbortSignal,
): Promise<void> {
  try {
    for await (const event of streamChat(sessionId, run.goal, signal, {
      mode: "agent",
      clientMessageId: crypto.randomUUID(),
    })) {
      applyEvent(run, event);
    }
    if (isAgentRunActive(run.status)) {
      run.status = "failed";
      run.error = "研究连接中断，请重试。";
      run.finishedAt = Date.now();
    }
  } catch (error) {
    if (isAbortError(error)) {
      run.status = "stopped";
    } else {
      run.status = "failed";
      run.error = toErrorMessage(error, "研究失败，请重试");
    }
    run.finishedAt = Date.now();
  } finally {
    controllers.delete(run.localId);
  }
}

function startRun(input: {
  sessionId: string;
  goal: string;
  paperId?: string;
}): AgentRunViewModel | null {
  const goal = input.goal.trim();
  if (!goal) {
    return null;
  }
  const existing = runs.value.find(
    (run) => run.sessionId === input.sessionId && isAgentRunActive(run.status),
  );
  if (existing) {
    activeLocalId.value = existing.localId;
    return existing;
  }

  runs.value.push({
    localId: crypto.randomUUID(),
    id: "",
    sessionId: input.sessionId,
    paperId: input.paperId,
    goal,
    status: "planning",
    steps: [],
    answer: "",
    sources: [],
    createdAt: Date.now(),
  });
  const run = runs.value[runs.value.length - 1];
  activeLocalId.value = run.localId;

  const controller = new AbortController();
  controllers.set(run.localId, controller);
  void consume(run, input.sessionId, controller.signal);
  return run;
}

function stopRun(localId?: string): void {
  const target =
    runs.value.find((run) => run.localId === (localId ?? activeLocalId.value)) ??
    runningRun.value;
  if (!target || !isAgentRunActive(target.status)) {
    return;
  }
  target.status = "stopped";
  target.finishedAt = Date.now();
  controllers.get(target.localId)?.abort();
}

function toViewModel(sessionId: string, detail: AgentRunDetail): AgentRunViewModel {
  return {
    localId: detail.id,
    id: detail.id,
    sessionId,
    goal: detail.question || "历史研究",
    status: detail.status,
    steps: (detail.steps ?? []).map((step) => ({
      step: step.step_index,
      tool: step.tool_name || step.kind,
      arguments: step.arguments ?? undefined,
      status: step.status,
      summary: step.summary ?? undefined,
      sources: step.sources ?? [],
      startedAt: Date.parse(step.created_at) || Date.now(),
      finishedAt: step.latency_ms
        ? (Date.parse(step.created_at) || Date.now()) + step.latency_ms
        : undefined,
      error: step.error_message ?? undefined,
    })),
    answer: detail.answer ?? "",
    sources: detail.sources ?? [],
    maxSteps: detail.max_steps,
    createdAt: Date.parse(detail.created_at) || Date.now(),
    finishedAt: detail.finished_at ? Date.parse(detail.finished_at) : undefined,
    error: detail.error_message ?? undefined,
  };
}

async function loadRun(sessionId: string, runId: string): Promise<AgentRunViewModel | null> {
  const cached = runs.value.find((run) => run.id === runId);
  if (cached) {
    activeLocalId.value = cached.localId;
    return cached;
  }
  try {
    const detail = await fetchAgentRun(sessionId, runId);
    const run = toViewModel(sessionId, detail);
    runs.value.push(run);
    activeLocalId.value = run.localId;
    return run;
  } catch {
    return null;
  }
}

function setActive(localId: string | null): void {
  activeLocalId.value = localId;
}

function latestRunForSession(sessionId: string): AgentRunViewModel | null {
  return (
    [...runs.value]
      .reverse()
      .find((run) => run.sessionId === sessionId) ?? null
  );
}

function reset(): void {
  controllers.forEach((controller) => controller.abort());
  controllers.clear();
  runs.value = [];
  activeLocalId.value = null;
}

export function useAgentRuns() {
  return {
    runs,
    activeLocalId,
    currentRun,
    runningRun,
    latestRunForSession,
    startRun,
    stopRun,
    loadRun,
    setActive,
    reset,
  };
}

export function resetAgentRuns(): void {
  reset();
}
