"""Framework-free agent contracts.

LangChain/LangGraph types stay in ``adapters/agent``; the rest of the backend
talks to this module only.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from backend.domain.models import SourceRef


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Request identity passed to every tool call."""

    session_id: str
    user_id: str | None = None


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


@dataclass(frozen=True, slots=True)
class AgentWarning:
    message: str


AgentEvent = AgentToken | AgentToolCall | AgentToolResult | AgentCompleted | AgentWarning


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
