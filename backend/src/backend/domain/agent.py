"""Framework-free agent contracts.

LangChain/LangGraph types stay in ``adapters/agent``; the rest of the backend
talks to this module only.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from backend.domain.models import SourceRef
from backend.domain.ports import Reranker, VectorStore


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Request identity and retrieval capabilities passed to every tool call."""

    session_id: str
    store: VectorStore
    user_id: str | None = None
    reranker: Reranker | None = None


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """A read-only tool exposed to the model."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Normalized tool output shared by every agent tool."""

    ok: bool
    content: str
    summary: str = ""
    sources: tuple[SourceRef, ...] = ()
    error: str | None = None

    @classmethod
    def failure(cls, message: str) -> "ToolResult":
        return cls(ok=False, content="", summary=message, error=message)


@dataclass(frozen=True, slots=True)
class AgentStarted:
    run_id: str
    max_steps: int


@dataclass(frozen=True, slots=True)
class AgentToken:
    text: str


@dataclass(frozen=True, slots=True)
class AgentToolCall:
    run_id: str
    step: int
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentToolResult:
    run_id: str
    step: int
    tool: str
    status: Literal["ok", "error"]
    summary: str
    sources: tuple[SourceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentCompleted:
    run_id: str
    answer: str
    sources: tuple[SourceRef, ...] = ()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class AgentWarning:
    message: str


@dataclass(frozen=True, slots=True)
class AgentFailed:
    run_id: str
    message: str
    partial_answer: str = ""


AgentEvent = (
    AgentStarted
    | AgentToken
    | AgentToolCall
    | AgentToolResult
    | AgentCompleted
    | AgentWarning
    | AgentFailed
)


class AgentRunner(Protocol):
    """Streams one agent run. Implementations own the framework loop."""

    def stream(
        self,
        *,
        question: str,
        history: list[dict],
        ctx: ToolContext,
        run_id: str,
    ) -> Iterator[AgentEvent]: ...
