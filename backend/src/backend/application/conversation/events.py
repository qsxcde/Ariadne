"""Streaming events emitted by application use cases.

These are transport-agnostic: the HTTP layer (``backend.api.streaming``) is
responsible for turning them into SSE frames.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from backend.domain.models import SourceRef


@dataclass(frozen=True, slots=True)
class StatusEvent:
    value: str


@dataclass(frozen=True, slots=True)
class RunStartedEvent:
    run_id: str
    max_steps: int


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    run_id: str
    step: int
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResultEvent:
    run_id: str
    step: int
    tool: str
    status: Literal["ok", "error"]
    summary: str
    sources: list[SourceRef] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class TokenEvent:
    value: str


@dataclass(frozen=True, slots=True)
class SourcesEvent:
    value: list[SourceRef]


@dataclass(frozen=True, slots=True)
class WarningEvent:
    value: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    value: str


@dataclass(frozen=True, slots=True)
class DoneEvent:
    run_id: str | None = None


ChatEvent = (
    StatusEvent
    | RunStartedEvent
    | ToolCallEvent
    | ToolResultEvent
    | TokenEvent
    | SourcesEvent
    | WarningEvent
    | ErrorEvent
    | DoneEvent
)
