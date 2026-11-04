"""Agent run lifecycle: budgets, product trace and citation validation."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from backend.config import settings
from backend.domain.agent import (
    AgentCompleted,
    AgentEvent,
    AgentFailed,
    AgentRunner,
    AgentStarted,
    AgentToken,
    AgentToolCall,
    AgentToolResult,
    AgentWarning,
    ToolContext,
)
from backend.domain.models import SourceRef
from backend.domain.states import AgentRunStatus, AgentStepKind, AgentStepStatus
from backend.rag.answer import CITATION_PATTERN
from backend.storage.sqlite import agent_runs as run_repo

logger = logging.getLogger(__name__)


class AgentBudgetExceededError(RuntimeError):
    """Raised when a run exceeds its tool-call budget."""


class AgentTimeoutError(RuntimeError):
    """Raised when a run exceeds its wall-clock budget."""


def _source_key(source: SourceRef) -> tuple[str, str, int]:
    return (source.paper_id or "", source.section, source.chunk_index)


def _dedupe_sources(sources: list[SourceRef]) -> tuple[SourceRef, ...]:
    seen: set[tuple[str, str, int]] = set()
    result: list[SourceRef] = []
    for source in sources:
        key = _source_key(source)
        if key not in seen:
            seen.add(key)
            result.append(source)
    return tuple(result)


def _citations_are_valid(answer: str, sources: tuple[SourceRef, ...]) -> bool:
    valid: dict[str, set[int]] = {}
    for source in sources:
        valid.setdefault(source.section, set()).add(source.chunk_index)
    citations = CITATION_PATTERN.findall(answer)
    if not citations:
        return False
    for section, chunk_index in citations:
        indexes = valid.get(section.strip())
        if indexes is None:
            return False
        if chunk_index and int(chunk_index) not in indexes:
            return False
    return True


def _fail_run(
    run_id: str,
    message: str,
    *,
    step_ids: dict[int, str],
    open_steps: set[int],
    step_count: int,
    token_text: list[str],
) -> AgentFailed:
    for step_index in open_steps:
        step_id = step_ids.get(step_index)
        if step_id is not None:
            run_repo.finish_agent_step(
                step_id,
                AgentStepStatus.interrupted,
                error_message=message,
            )
    run_repo.finish_agent_run(
        run_id,
        AgentRunStatus.failed,
        step_count=step_count,
        error_message=message,
    )
    return AgentFailed(
        run_id=run_id,
        message=message,
        partial_answer="".join(token_text),
    )


def stream_agent_run(
    *,
    runner: AgentRunner,
    session_id: str,
    question: str,
    history: list[dict],
    ctx: ToolContext,
    client_message_id: str | None = None,
    model: str | None = None,
) -> Iterator[AgentEvent]:
    """Create a run, relay adapter events, and persist the step ledger."""
    run = run_repo.create_agent_run(
        session_id,
        user_id=ctx.user_id,
        client_message_id=client_message_id,
        model=model,
        max_steps=settings.agent_max_steps,
    )
    run_id = run["id"]
    yield AgentStarted(run_id=run_id, max_steps=run["max_steps"])

    started = time.monotonic()
    step_ids: dict[int, str] = {}
    open_steps: set[int] = set()
    token_text: list[str] = []
    sources: list[SourceRef] = []

    try:
        for event in runner.stream(
            question=question,
            history=history,
            ctx=ctx,
            run_id=run_id,
        ):
            if time.monotonic() - started > settings.agent_timeout_seconds:
                raise AgentTimeoutError("Agent 运行超时，请缩小问题范围后重试。")

            if isinstance(event, AgentToken):
                token_text.append(event.text)
                yield event
            elif isinstance(event, AgentToolCall):
                if len(step_ids) >= settings.agent_max_tool_calls:
                    raise AgentBudgetExceededError(
                        f"工具调用次数超出上限（{settings.agent_max_tool_calls}）。"
                    )
                step = run_repo.create_agent_step(
                    run_id,
                    event.step,
                    AgentStepKind.tool,
                    tool_name=event.tool,
                    arguments=event.arguments,
                )
                step_ids[event.step] = step["id"]
                open_steps.add(event.step)
                yield event
            elif isinstance(event, AgentToolResult):
                step_id = step_ids.get(event.step)
                if step_id is not None:
                    open_steps.discard(event.step)
                    run_repo.finish_agent_step(
                        step_id,
                        AgentStepStatus.ok
                        if event.status == "ok"
                        else AgentStepStatus.error,
                        sources=[source.model_dump() for source in event.sources],
                        summary=event.summary,
                        error_message=event.summary if event.status == "error" else None,
                    )
                sources.extend(event.sources)
                yield event
            elif isinstance(event, AgentWarning):
                yield event
            elif isinstance(event, AgentCompleted):
                answer = event.answer or "".join(token_text)
                union = _dedupe_sources([*sources, *event.sources])
                if not _citations_are_valid(answer, union):
                    yield AgentWarning(message=settings.msg_no_valid_citations)
                run_repo.finish_agent_run(
                    run_id,
                    AgentRunStatus.completed,
                    step_count=len(step_ids),
                    prompt_tokens=event.prompt_tokens,
                    completion_tokens=event.completion_tokens,
                )
                yield AgentCompleted(
                    run_id=run_id,
                    answer=answer,
                    sources=union,
                    prompt_tokens=event.prompt_tokens,
                    completion_tokens=event.completion_tokens,
                )
                return
    except GeneratorExit:
        for step_index in open_steps:
            step_id = step_ids.get(step_index)
            if step_id is not None:
                run_repo.finish_agent_step(
                    step_id,
                    AgentStepStatus.interrupted,
                    error_message="客户端已停止",
                )
        run_repo.finish_agent_run(
            run_id,
            AgentRunStatus.stopped,
            step_count=len(step_ids),
            error_message="客户端已停止",
        )
        raise
    except Exception as exc:
        logger.exception("Agent run failed: run_id=%s", run_id)
        message = str(exc) or "Agent 运行失败，请重试。"
        yield _fail_run(
            run_id,
            message[:300],
            step_ids=step_ids,
            open_steps=open_steps,
            step_count=len(step_ids),
            token_text=token_text,
        )
        return

    yield _fail_run(
        run_id,
        "Agent 未产生最终回答。",
        step_ids=step_ids,
        open_steps=open_steps,
        step_count=len(step_ids),
        token_text=token_text,
    )
