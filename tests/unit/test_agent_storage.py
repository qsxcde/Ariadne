"""Schema v19 migration and agent run repository tests."""

import sqlite3

from backend.domain.states import AgentRunStatus, AgentStepKind, AgentStepStatus
from backend.storage.paths import agent_checkpoint_path
from backend.storage.sqlite.agent_runs import (
    create_agent_run,
    create_agent_step,
    finish_agent_run,
    finish_agent_step,
    get_agent_run,
    get_agent_run_by_client_message_id,
    list_agent_runs,
    list_agent_steps,
)
from backend.storage.sqlite.messages import create_message, get_message
from backend.storage.sqlite.migrations import migrate_schema
from backend.storage.sqlite.sessions import create_session


def test_v18_database_migrates_to_v19(tmp_path) -> None:
    conn = sqlite3.connect(tmp_path / "legacy.db")
    conn.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY);
        CREATE TABLE messages (
          id TEXT PRIMARY KEY,
          session_id TEXT NOT NULL,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          sources_json TEXT NULL,
          status TEXT NOT NULL,
          client_message_id TEXT NULL,
          model TEXT NULL,
          prompt_tokens INTEGER NULL,
          completion_tokens INTEGER NULL,
          created_at TEXT NOT NULL
        );
        INSERT INTO sessions (id) VALUES ('session-1');
        INSERT INTO messages (
          id, session_id, role, content, status, created_at
        ) VALUES ('message-1', 'session-1', 'user', 'legacy question', 'complete', '2026-01-01');
        """
    )
    migrate_schema(conn, 18)
    conn.commit()

    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"agent_runs", "agent_steps"} <= tables

    message_columns = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
    assert "run_id" in message_columns

    legacy = conn.execute("SELECT content, run_id FROM messages WHERE id = 'message-1'").fetchone()
    assert legacy == ("legacy question", None)
    conn.close()


def test_agent_run_and_step_lifecycle(isolated_storage) -> None:
    session = create_session("Agent session")
    run = create_agent_run(
        session["id"],
        client_message_id="client-1",
        model="deepseek-chat",
        max_steps=4,
    )
    assert run["status"] == AgentRunStatus.running
    assert run["step_count"] == 0
    assert run["max_steps"] == 4

    step = create_agent_step(
        run["id"],
        0,
        AgentStepKind.tool,
        tool_name="search_session_chunks",
        arguments={"query": "attention"},
    )
    finish_agent_step(
        step["id"],
        AgentStepStatus.ok,
        result={"ok": True, "content": "preview"},
        sources=[{"section": "Introduction", "chunk_index": 2}],
        summary="命中 1 个片段",
        latency_ms=12,
    )
    finish_agent_run(
        run["id"],
        AgentRunStatus.completed,
        step_count=1,
        prompt_tokens=30,
        completion_tokens=50,
    )

    stored = get_agent_run(run["id"])
    assert stored is not None
    assert stored["status"] == AgentRunStatus.completed
    assert stored["step_count"] == 1
    assert stored["prompt_tokens"] == 30
    assert stored["finished_at"] is not None

    steps = list_agent_steps(run["id"])
    assert [item["step_index"] for item in steps] == [0]
    assert steps[0]["arguments"] == {"query": "attention"}
    assert steps[0]["result"] == {"ok": True, "content": "preview"}
    assert steps[0]["sources"] == [{"section": "Introduction", "chunk_index": 2}]
    assert steps[0]["summary"] == "命中 1 个片段"
    assert steps[0]["latency_ms"] == 12


def test_agent_run_client_message_is_idempotent(isolated_storage) -> None:
    session = create_session("Agent session")
    first = create_agent_run(session["id"], client_message_id="same-client-id")
    second = create_agent_run(session["id"], client_message_id="same-client-id")
    assert first["id"] == second["id"]
    assert get_agent_run_by_client_message_id("same-client-id")["id"] == first["id"]
    assert len(list_agent_runs(session["id"])) == 1


def test_message_carries_run_id(isolated_storage) -> None:
    session = create_session("Agent session")
    run = create_agent_run(session["id"])
    message = create_message(
        session["id"],
        "assistant",
        "answer",
        run_id=run["id"],
    )
    assert message["run_id"] == run["id"]
    assert get_message(message["id"])["run_id"] == run["id"]

    plain = create_message(session["id"], "user", "question")
    assert plain["run_id"] is None


def test_agent_checkpoint_path_uses_data_dir(isolated_storage) -> None:
    path = agent_checkpoint_path()
    assert path == isolated_storage / "data" / "agent" / "checkpoints.sqlite"
    assert path.parent.is_dir()
