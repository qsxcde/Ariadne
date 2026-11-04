import { requestJson } from "@/api/client";
import type { AgentRunDetail, FeatureFlags } from "@/api/types";

/** 读取服务端当前开放的功能开关。 */
export function fetchFeatures(): Promise<FeatureFlags> {
  return requestJson<FeatureFlags>("/features", "读取功能开关失败");
}

/** 回放一次 Agent 运行的轨迹（run + steps）。 */
export function fetchAgentRun(sessionId: string, runId: string): Promise<AgentRunDetail> {
  return requestJson<AgentRunDetail>(
    `/sessions/${sessionId}/runs/${runId}`,
    "读取研究过程失败",
  );
}
