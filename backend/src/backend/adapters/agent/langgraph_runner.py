"""LangGraph implementation of :class:`AgentRunner`.

Only this module (and ``langchain_tools``) may import LangChain/LangGraph.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from typing import Any, cast

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import SecretStr

from backend.adapters.agent.langchain_tools import build_langchain_tools
from backend.application.agent.tools.session_tools import SessionTools
from backend.application.model_settings.service import resolve_llm
from backend.config import settings
from backend.domain.agent import (
    AgentCompleted,
    AgentEvent,
    AgentToken,
    AgentToolCall,
    AgentToolResult,
    ToolContext,
)
from backend.domain.models import SourceRef
from backend.prompts.loader import load_prompt
from backend.storage.paths import agent_checkpoint_path

logger = logging.getLogger(__name__)


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


def _parse_tool_payload(content: Any) -> tuple[str, str, tuple[SourceRef, ...]]:
    """Return (status, summary, sources) from a tool JSON payload."""
    text = content if isinstance(content, str) else str(content)
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return "ok", text[:200], ()
    if not isinstance(payload, dict):
        return "ok", text[:200], ()
    status = "ok" if payload.get("ok") else "error"
    summary = str(payload.get("summary") or payload.get("error") or text[:200])
    sources: list[SourceRef] = []
    for raw in payload.get("sources") or []:
        try:
            sources.append(SourceRef.model_validate(raw))
        except Exception:
            logger.debug("Skipping malformed agent tool source: %r", raw)
    return status, summary, tuple(sources)


class LangGraphAgentRunner:
    """Streams one LangGraph agent run with a per-run SQLite checkpointer."""

    def __init__(
        self,
        *,
        max_steps: int | None = None,
        max_history_turns: int | None = None,
    ) -> None:
        self._max_steps = max_steps or settings.agent_max_steps
        self._max_history_turns = max_history_turns or settings.agent_max_history_turns

    def _build_messages(
        self, question: str, history: list[dict]
    ) -> list[BaseMessage]:
        turns = history[-self._max_history_turns * 2 :]
        messages: list[BaseMessage] = []
        pending_user: str | None = None
        for turn in turns:
            role = turn.get("role")
            content = turn.get("content")
            if not isinstance(content, str) or not content:
                continue
            if role == "user":
                pending_user = content
            elif role == "assistant" and pending_user is not None:
                messages.append(HumanMessage(content=pending_user))
                messages.append(AIMessage(content=content))
                pending_user = None
        messages.append(HumanMessage(content=question))
        return messages

    def stream(
        self,
        *,
        question: str,
        history: list[dict],
        ctx: ToolContext,
        run_id: str,
    ) -> Iterator[AgentEvent]:
        config = resolve_llm(ctx.user_id)
        model = ChatOpenAI(
            model=config.model,
            api_key=SecretStr(config.api_key),
            base_url=config.base_url,
            temperature=0,
            timeout=settings.agent_timeout_seconds,
            max_retries=2,
            max_completion_tokens=settings.llm_max_tokens,
            streaming=True,
        )
        session_tools = SessionTools(
            session_id=ctx.session_id,
            user_id=ctx.user_id,
            store=ctx.store,
            reranker=ctx.reranker,
            preview_chars=settings.agent_tool_preview_chars,
            max_evidence_chars=settings.agent_max_evidence_chars,
        )

        conn = sqlite3.connect(
            str(agent_checkpoint_path()),
            check_same_thread=False,
            timeout=30,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            agent = create_agent(
                model=model,
                tools=build_langchain_tools(session_tools),
                system_prompt=load_prompt("agent_system"),
                checkpointer=SqliteSaver(conn),
                middleware=[
                    ModelCallLimitMiddleware(
                        run_limit=self._max_steps,
                        exit_behavior="error",
                    )
                ],
            )
            yield from self._stream_agent(
                agent,
                messages=self._build_messages(question, history),
                run_id=run_id,
            )
        finally:
            conn.close()

    def _stream_agent(
        self,
        agent: Any,
        *,
        messages: list[BaseMessage],
        run_id: str,
    ) -> Iterator[AgentEvent]:
        token_text: list[str] = []
        answer = ""
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        step_counter = 0
        call_steps: dict[str, int] = {}
        call_names: dict[str, str] = {}
        sources: list[SourceRef] = []

        events = agent.stream(
            {"messages": messages},
            config={
                "configurable": {"thread_id": run_id},
                # The model-call middleware owns the real step budget; this is
                # only a safety net, so keep it above the middleware threshold.
                "recursion_limit": self._max_steps * 4 + 4,
            },
            stream_mode=["updates", "messages"],
        )
        for mode, chunk in events:
            if mode == "messages":
                message, metadata = cast(tuple[Any, dict], chunk)
                if metadata.get("langgraph_node") != "model":
                    continue
                content = getattr(message, "content", None)
                if (
                    isinstance(content, str)
                    and content
                    and not getattr(message, "tool_calls", None)
                    and not getattr(message, "tool_call_chunks", None)
                ):
                    token_text.append(content)
                    yield AgentToken(text=content)
                continue

            update = cast(dict[str, Any], chunk)
            for node_update in update.values():
                if not isinstance(node_update, dict):
                    continue
                for message in node_update.get("messages", []):
                    if isinstance(message, AIMessage):
                        if message.tool_calls:
                            for call in message.tool_calls:
                                call_id = str(call.get("id") or f"call-{step_counter + 1}")
                                step_counter += 1
                                call_steps[call_id] = step_counter
                                call_names[call_id] = str(call.get("name") or "unknown")
                                yield AgentToolCall(
                                    run_id=run_id,
                                    step=step_counter,
                                    tool=call_names[call_id],
                                    arguments=dict(call.get("args") or {}),
                                )
                        elif isinstance(message.content, str) and message.content.strip():
                            answer = message.content
                            usage = cast(dict[str, Any], message.usage_metadata or {})
                            prompt_tokens = usage.get("input_tokens")
                            completion_tokens = usage.get("output_tokens")
                    elif isinstance(message, ToolMessage):
                        call_id = str(message.tool_call_id or "")
                        step = call_steps.get(call_id, step_counter)
                        status, summary, tool_sources = _parse_tool_payload(message.content)
                        sources.extend(tool_sources)
                        yield AgentToolResult(
                            run_id=run_id,
                            step=step,
                            tool=call_names.get(call_id, str(message.name or "unknown")),
                            status=cast(Any, status),
                            summary=summary,
                            sources=tool_sources,
                        )

        yield AgentCompleted(
            run_id=run_id,
            answer=answer or "".join(token_text),
            sources=_dedupe_sources(sources),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
