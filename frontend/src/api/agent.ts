import { requestJson } from "@/api/client";
import type { AgentRunDetail } from "@/api/types";

/** 回放一次 Agent 运行的轨迹（run + steps）。 */
export function fetchAgentRun(sessionId: string, runId: string): Promise<AgentRunDetail> {
  return requestJson<AgentRunDetail>(
    `/sessions/${sessionId}/runs/${runId}`,
    "读取研究过程失败",
  );
}
