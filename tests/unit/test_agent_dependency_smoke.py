"""Dependency gate for the LangChain/LangGraph agent stack.

These tests exercise the framework without a real model or network call so
that a broken upgrade fails in CI before any agent code is written.
"""

import json
import sqlite3
from typing import Any

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from openai import OpenAI
from pydantic import PrivateAttr


class ScriptedToolCallingModel(BaseChatModel):
    """First turn calls ``echo``; later turns answer from the tool result."""

    _turn: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted-tool-calling"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedToolCallingModel":
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._turn += 1
        if self._turn == 1:
            message = AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"text": "ping"}, "id": "call-1"}],
            )
        else:
            message = AIMessage(content="answer: ping")
        return ChatResult(generations=[ChatGeneration(message=message)])


@tool
def echo(text: str) -> str:
    """Return the provided text unchanged."""
    return text


def _checkpoint_agent(path: Any) -> tuple[Any, sqlite3.Connection, dict[str, Any]]:
    conn = sqlite3.connect(path, check_same_thread=False)
    agent = create_agent(
        model=ScriptedToolCallingModel(),
        tools=[echo],
        system_prompt="Use tools when needed.",
        checkpointer=SqliteSaver(conn),
    )
    return agent, conn, {"configurable": {"thread_id": "run-1"}}


@pytest.mark.unit
def test_create_agent_completes_tool_loop(tmp_path: Any) -> None:
    agent, conn, config = _checkpoint_agent(tmp_path / "checkpoints.sqlite")
    result = agent.invoke({"messages": [HumanMessage("please echo")]}, config)

    messages = result["messages"]
    assert any(isinstance(message, AIMessage) and message.tool_calls for message in messages)
    assert any(
        isinstance(message, AIMessage) and not message.tool_calls and message.content == "answer: ping"
        for message in messages
    )
    conn.close()


@pytest.mark.unit
def test_sqlite_saver_reloads_thread(tmp_path: Any) -> None:
    path = tmp_path / "checkpoints.sqlite"
    agent, conn, config = _checkpoint_agent(path)
    agent.invoke({"messages": [HumanMessage("please echo")]}, config)
    conn.close()

    conn2 = sqlite3.connect(path, check_same_thread=False)
    try:
        saver2 = SqliteSaver(conn2)
        restored = saver2.get_tuple(config)
        assert restored is not None
        assert restored.checkpoint["channel_values"]["messages"][-1].content == "answer: ping"
    finally:
        conn2.close()


@pytest.mark.unit
def test_stream_exposes_updates_and_message_tokens(tmp_path: Any) -> None:
    agent, conn, config = _checkpoint_agent(tmp_path / "checkpoints.sqlite")
    try:
        events = list(
            agent.stream(
                {"messages": [HumanMessage("please echo")]},
                config,
                stream_mode=["updates", "messages"],
            )
        )
    finally:
        conn.close()

    modes = {mode for mode, _ in events}
    assert modes == {"updates", "messages"}
    tokens = "".join(
        chunk[0].content
        for mode, chunk in events
        if mode == "messages" and isinstance(chunk[0].content, str)
    )
    assert "answer: ping" in tokens
    assert any(mode == "updates" and chunk for mode, chunk in events)


def _mock_openai(handler: Any) -> OpenAI:
    return OpenAI(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.unit
def test_openai_sdk_accepts_chat_completions_params() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.read()))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    response = _mock_openai(handler).chat.completions.create(
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
        temperature=0,
        max_tokens=16,
    )
    assert response.choices[0].message.content == "ok"
    assert captured["max_tokens"] == 16
    assert captured["temperature"] == 0


@pytest.mark.unit
def test_openai_sdk_streams_usage_chunk() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.read()))
        chunks = [
            {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "test-model",
                "choices": [{"index": 0, "delta": {"content": "hello"}, "finish_reason": None}],
            },
            {
                "id": "chatcmpl-1",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": "test-model",
                "choices": [],
                "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            },
        ]
        body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    stream = _mock_openai(handler).chat.completions.create(
        model="test-model",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
        stream_options={"include_usage": True},
        max_tokens=16,
    )
    received = list(stream)
    assert captured["stream"] is True
    assert captured["stream_options"] == {"include_usage": True}
    assert received[0].choices[0].delta.content == "hello"
    assert received[-1].usage is not None
    assert received[-1].usage.completion_tokens == 2


@pytest.mark.unit
def test_chat_openai_accepts_custom_base_url() -> None:
    model = ChatOpenAI(
        model="deepseek-v4-flash",
        api_key="test-key",
        base_url="https://example.invalid/v1",
        temperature=0,
        max_retries=0,
    )
    assert model.model_name == "deepseek-v4-flash"
    assert model.openai_api_base == "https://example.invalid/v1"
