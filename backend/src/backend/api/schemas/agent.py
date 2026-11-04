"""Agent run and step transfer models."""

from pydantic import BaseModel, Field

from backend.domain.models import SourceRef
from backend.domain.states import AgentRunStatus, AgentStepKind, AgentStepStatus


class AgentStepSummary(BaseModel):
    id: str
    run_id: str
    step_index: int
    kind: AgentStepKind
    tool_name: str | None = None
    arguments: dict | None = None
    result: dict | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    summary: str | None = None
    status: AgentStepStatus
    error_message: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    created_at: str


class AgentRunDetail(BaseModel):
    id: str
    session_id: str
    user_id: str | None = None
    client_message_id: str | None = None
    status: AgentRunStatus
    model: str | None = None
    max_steps: int
    step_count: int
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error_message: str | None = None
    created_at: str
    finished_at: str | None = None
    steps: list[AgentStepSummary] = Field(default_factory=list)
