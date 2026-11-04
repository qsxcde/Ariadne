"""Adapters: LangGraph event mapping, checkpointing and model-call budget."""

import importlib
from typing import Any

import pytest
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from backend.domain.agent import (
    AgentCompleted,
    AgentToken,
    AgentToolCall,
    AgentToolResult,
    ToolContext,
)
from backend.storage.paths import agent_checkpoint_path
from backend.storage.sqlite import sessions as session_repo

runner_module = importlib.import_module("backend.adapters.agent.langgraph_runner")


class ScriptedToolModel(BaseChatModel):
    _tool_name: str = PrivateAttr(default="search_session_chunks")
    _tool_args: dict = PrivateAttr(default_factory=lambda: {"query": "attention"})
    _final: str = PrivateAttr(default="final answer")
    _calls: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-model"

    def script(self, tool_name: str, args: dict, final: str = "final answer") -> None:
        self._tool_name = tool_name
        self._tool_args = args
        self._final = final

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedToolModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls += 1
        if any(isinstance(message, AIMessage) and message.tool_calls for message in messages):
            message = AIMessage(content=self._final)
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self._tool_name,
                        "args": self._tool_args,
                        "id": f"call-{self._calls}",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


class AlwaysToolModel(ScriptedToolModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._calls += 1
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": self._tool_name,
                    "args": self._tool_args,
                    "id": f"call-{self._calls}",
                }
            ],
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


class EmptyStore:
    def list_chunks(self):
        return []

    def search(self, query, k=5):
        return []

    def search_with_ranks(self, query, k=5):
        return []


def _install_fake_model(monkeypatch, model: BaseChatModel) -> None:
    monkeypatch.setattr(
        runner_module,
        "resolve_llm",
        lambda user_id: type(
            "Config",
            (),
            {
                "model": "fake-model",
                "base_url": "https://example.invalid/v1",
                "api_key": "test-key",
                "provider": "fake",
            },
        )(),
    )
    monkeypatch.setattr(runner_module, "ChatOpenAI", lambda **kwargs: model)


def _context(session_id: str) -> ToolContext:
    return ToolContext(session_id=session_id, user_id="u1", store=EmptyStore())


def test_runner_streams_tool_call_and_completion(isolated_storage, monkeypatch) -> None:
    session = session_repo.create_session("Agent", user_id="u1")
    model = ScriptedToolModel()
    _install_fake_model(monkeypatch, model)

    events = list(
        runner_module.LangGraphAgentRunner(max_steps=4).stream(
            question="attention?",
            history=[],
            ctx=_context(session["id"]),
            run_id="run-1",
        )
    )

    assert any(isinstance(event, AgentToolCall) for event in events)
    tool_result = next(event for event in events if isinstance(event, AgentToolResult))
    assert tool_result.step == 1
    assert tool_result.status == "ok"
    assert any(isinstance(event, AgentToken) for event in events)
    completed = events[-1]
    assert isinstance(completed, AgentCompleted)
    assert completed.answer == "final answer"
    assert agent_checkpoint_path().is_file()


def test_runner_reports_tool_errors_as_data(isolated_storage, monkeypatch) -> None:
    session = session_repo.create_session("Agent", user_id="u1")
    model = ScriptedToolModel()
    model.script(
        "read_chunk",
        {"paper_id": "missing-document", "section": "Introduction", "chunk_index": 0},
    )
    _install_fake_model(monkeypatch, model)

    events = list(
        runner_module.LangGraphAgentRunner(max_steps=4).stream(
            question="q",
            history=[],
            ctx=_context(session["id"]),
            run_id="run-error",
        )
    )

    tool_result = next(event for event in events if isinstance(event, AgentToolResult))
    assert tool_result.status == "error"
    assert "无权访问" in tool_result.summary


def test_runner_enforces_model_call_limit(isolated_storage, monkeypatch) -> None:
    session = session_repo.create_session("Agent", user_id="u1")
    _install_fake_model(monkeypatch, AlwaysToolModel())

    with pytest.raises(ModelCallLimitExceededError):
        list(
            runner_module.LangGraphAgentRunner(max_steps=2).stream(
                question="loop",
                history=[],
                ctx=_context(session["id"]),
                run_id="run-loop",
            )
        )
