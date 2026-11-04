"""LangGraph adapter event mapping and run lifecycle tests."""

from types import SimpleNamespace

import pytest

from backend.application.agent.service import stream_agent_run
from backend.domain.agent import (
    AgentCompleted,
    AgentFailed,
    AgentStarted,
    AgentToken,
    AgentToolCall,
    AgentToolResult,
    AgentWarning,
    ToolContext,
)
from backend.domain.models import SourceRef
from backend.storage.sqlite import agent_runs as run_repo
from backend.storage.sqlite import sessions as session_repo


class StubRunner:
    def __init__(self, build_events):
        self._build_events = build_events

    def stream(self, *, question, history, ctx, run_id):
        yield from self._build_events(run_id)


def _context(session_id: str) -> ToolContext:
    return ToolContext(session_id=session_id, user_id="u1", store=SimpleNamespace())


def _source() -> SourceRef:
    return SourceRef(paper_id="doc-1", section="Introduction", chunk_index=0)


def test_agent_run_persists_trace_and_sources(isolated_storage) -> None:
    session = session_repo.create_session("Agent", user_id="u1")
    source = _source()

    def events(run_id: str):
        yield AgentToken("结论")
        yield AgentToolCall(run_id, 1, "search_session_chunks", {"query": "attention"})
        yield AgentToolResult(run_id, 1, "search_session_chunks", "ok", "命中 1 个片段", (source,))
        yield AgentCompleted(
            run_id,
            "结论 [Section: Introduction | Chunk: 0]",
            (source,),
            12,
            34,
        )

    result = list(
        stream_agent_run(
            runner=StubRunner(events),
            session_id=session["id"],
            question="attention?",
            history=[],
            ctx=_context(session["id"]),
            model="fake-model",
        )
    )

    assert isinstance(result[0], AgentStarted)
    completed = result[-1]
    assert isinstance(completed, AgentCompleted)
    assert completed.sources == (source,)

    run = run_repo.get_agent_run(result[0].run_id)
    assert run is not None
    assert run["status"] == "completed"
    assert run["step_count"] == 1
    assert run["prompt_tokens"] == 12
    assert run["completion_tokens"] == 34
    assert run["model"] == "fake-model"

    steps = run_repo.list_agent_steps(run["id"])
    assert len(steps) == 1
    assert steps[0]["status"] == "ok"
    assert steps[0]["tool_name"] == "search_session_chunks"
    assert steps[0]["arguments"] == {"query": "attention"}
    assert steps[0]["sources"] == [source.model_dump()]


def test_invalid_citations_emit_warning_but_keep_answer(isolated_storage) -> None:
    session = session_repo.create_session("Agent", user_id="u1")

    def events(run_id: str):
        yield AgentCompleted(run_id, "没有引用的答案", ())

    result = list(
        stream_agent_run(
            runner=StubRunner(events),
            session_id=session["id"],
            question="q",
            history=[],
            ctx=_context(session["id"]),
        )
    )

    warnings = [event for event in result if isinstance(event, AgentWarning)]
    assert warnings and "引用" in warnings[0].message
    assert isinstance(result[-1], AgentCompleted)


def test_abbreviated_section_citation_is_valid_when_chunk_matches(
    isolated_storage,
) -> None:
    session = session_repo.create_session("Agent", user_id="u1")
    source = SourceRef(
        paper_id="doc-1",
        section="III. Methods > A. Training > 5) Joint Training Objective",
        chunk_index=78,
    )

    def events(run_id: str):
        yield AgentCompleted(
            run_id,
            "结论 [Section: III. ... > 5) Joint Training Objective | Chunk: 78]",
            (source,),
        )

    result = list(
        stream_agent_run(
            runner=StubRunner(events),
            session_id=session["id"],
            question="q",
            history=[],
            ctx=_context(session["id"]),
        )
    )

    assert not [event for event in result if isinstance(event, AgentWarning)]


def test_tool_budget_marks_run_failed(isolated_storage, monkeypatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "agent_max_tool_calls", 1)
    session = session_repo.create_session("Agent", user_id="u1")

    def events(run_id: str):
        yield AgentToolCall(run_id, 1, "search_session_chunks", {"query": "a"})
        yield AgentToolResult(run_id, 1, "search_session_chunks", "ok", "hit", ())
        yield AgentToolCall(run_id, 2, "search_session_chunks", {"query": "b"})
        yield AgentCompleted(run_id, "done", ())

    result = list(
        stream_agent_run(
            runner=StubRunner(events),
            session_id=session["id"],
            question="q",
            history=[],
            ctx=_context(session["id"]),
        )
    )

    assert isinstance(result[-1], AgentFailed)
    run_id = result[0].run_id
    run = run_repo.get_agent_run(run_id)
    assert run is not None and run["status"] == "failed"
    assert run["step_count"] == 1


def test_timeout_marks_run_failed(isolated_storage, monkeypatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "agent_timeout_seconds", -1.0)
    session = session_repo.create_session("Agent", user_id="u1")

    def events(run_id: str):
        yield AgentToken("partial")
        yield AgentCompleted(run_id, "never", ())

    result = list(
        stream_agent_run(
            runner=StubRunner(events),
            session_id=session["id"],
            question="q",
            history=[],
            ctx=_context(session["id"]),
        )
    )

    assert isinstance(result[-1], AgentFailed)
    run = run_repo.get_agent_run(result[0].run_id)
    assert run is not None and run["status"] == "failed"


def test_client_stop_marks_run_stopped(isolated_storage) -> None:
    session = session_repo.create_session("Agent", user_id="u1")

    def events(run_id: str):
        yield AgentToken("first")
        yield AgentToken("second")

    generator = stream_agent_run(
        runner=StubRunner(events),
        session_id=session["id"],
        question="q",
        history=[],
        ctx=_context(session["id"]),
    )
    started = next(generator)
    next(generator)
    generator.close()

    run = run_repo.get_agent_run(started.run_id)
    assert run is not None and run["status"] == "stopped"
