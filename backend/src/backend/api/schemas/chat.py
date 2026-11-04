"""Chat transport models: request payload and the SSE event union."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.domain.models import SourceRef


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = "user"
    content: str
    """快速问答（单跳 RAG）或 Agent 多步研究。"""
    mode: Literal["fast", "agent"] = "fast"
    """为 true 时复用上一条用户提问，先删除旧回答再重新生成。"""
    regenerate: bool = False
    """客户端生成的消息 id，用于重试时去重（同一 id 只会落一条 user 消息）。"""
    client_message_id: str | None = None


class ChatStreamTokenEvent(BaseModel):
    type: Literal["token"]
    value: str


class ChatStreamStatusEvent(BaseModel):
    type: Literal["status"]
    value: Literal[
        "waiting_for_index",
        "retrieving",
        "generating",
        "planning",
        "tool_running",
        "answering",
    ]


class RunStartedValue(BaseModel):
    run_id: str
    max_steps: int


class ChatStreamRunStartedEvent(BaseModel):
    type: Literal["run_started"]
    value: RunStartedValue


class ToolCallValue(BaseModel):
    run_id: str
    step: int
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatStreamToolCallEvent(BaseModel):
    type: Literal["tool_call"]
    value: ToolCallValue


class ToolResultValue(BaseModel):
    run_id: str
    step: int
    tool: str
    status: Literal["ok", "error"]
    summary: str
    sources: list[SourceRef] = Field(default_factory=list)


class ChatStreamToolResultEvent(BaseModel):
    type: Literal["tool_result"]
    value: ToolResultValue


class ChatStreamSourcesEvent(BaseModel):
    type: Literal["sources"]
    value: list[SourceRef]


class ChatStreamErrorEvent(BaseModel):
    type: Literal["error"]
    value: str


class ChatStreamWarningEvent(BaseModel):
    type: Literal["warning"]
    value: str


class ChatStreamDoneEvent(BaseModel):
    type: Literal["done"]
    run_id: str | None = None


ChatStreamEvent = (
    ChatStreamStatusEvent
    | ChatStreamRunStartedEvent
    | ChatStreamToolCallEvent
    | ChatStreamToolResultEvent
    | ChatStreamTokenEvent
    | ChatStreamSourcesEvent
    | ChatStreamErrorEvent
    | ChatStreamWarningEvent
    | ChatStreamDoneEvent
)
