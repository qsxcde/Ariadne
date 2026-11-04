import type { SessionSummary, SourceRef } from "@/api";

/** 当前激活论文会话的轻量视图模型（侧栏 + 头部展示用）。 */
export type PaperSession = {
  sessionId: string;
  docId?: string;
  fileName: string;
  chunkCount: number;
  indexEmbedding?: IndexEmbeddingState | null;
};

/** 当前 Embedding 配置与活动索引是否匹配。 */
export type IndexEmbeddingState = {
  stale: boolean;
  current_model: string;
  current_mode: "remote" | "local";
  index_model?: string | null;
};

/** 聊天区渲染用的消息模型，与持久化实体解耦。 */
export type ChatMessageViewModel = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: SourceRef[];
  /** 该回答由哪次 Agent 运行产生；用于回放过程。 */
  runId?: string;
};

export type AgentRunStatus =
  | "planning"
  | "tool_running"
  | "answering"
  | "running"
  | "completed"
  | "failed"
  | "stopped";

export type AgentStepStatus = "running" | "ok" | "error" | "interrupted";

export type AgentStepViewModel = {
  step: number;
  tool: string;
  arguments?: Record<string, unknown>;
  status: AgentStepStatus;
  summary?: string;
  sources: SourceRef[];
  startedAt: number;
  finishedAt?: number;
  error?: string;
};

export type AgentRunViewModel = {
  localId: string;
  /** 服务端 run id；收到 run_started 前为空。 */
  id: string;
  sessionId: string;
  paperId?: string;
  goal: string;
  status: AgentRunStatus;
  steps: AgentStepViewModel[];
  answer: string;
  sources: SourceRef[];
  warning?: string;
  error?: string;
  maxSteps?: number;
  createdAt: number;
  finishedAt?: number;
};

export type SidebarSessionItem = {
  id: string;
  isPinned: boolean;
  title: string;
  description: string;
  active: boolean;
};

export type ComposerToolState = {
  isSearchSelected: boolean;
  isMoreMenuVisible: boolean;
};

export type SessionSummaryViewModel = SessionSummary & {
  active: boolean;
};

export type SessionActionTarget = {
  id: string;
  title: string;
};

type UploadPhase = "idle" | "uploading" | "parsing" | "indexing" | "ready" | "error";

export type UploadStatus = {
  fileName: string;
  fileSizeLabel: string;
  errorMessage?: string;
  phase: UploadPhase;
  /** 0-100，按后端处理阶段推算；ready 时为 100 */
  progress: number;
  /** 阶段文案，如「正在解析 PDF」 */
  stageLabel: string;
  /** 解析完成前为 false：阅读器必须等文档就绪才能打开 */
  canOpen: boolean;
};

export type SuggestedPrompt = {
  id: string;
  text: string;
};

/** 一次引用点击：序号用于角标，source 携带定位坐标。 */
export type SourceSelection = {
  index: number;
  source: SourceRef;
};

/** 阅读器大纲条目：key 用于高亮，blockId 用于跳转。 */
export type ReaderOutlineItem = {
  key: string;
  title: string;
  level: number;
  blockId: string;
  pageNumber: number;
};

/** 选区提问的两种意图。 */
export type SelectionAskMode = "explain" | "followup" | "translate" | "simplify";
