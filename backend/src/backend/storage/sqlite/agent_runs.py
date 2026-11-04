"""Persistence for agent runs and their step ledger."""

import json
import uuid
from typing import Any, cast

from backend.domain.states import AgentRunStatus, AgentStepKind, AgentStepStatus
from backend.storage.records import AgentRunRecord, AgentStepRecord
from backend.storage.sqlite.connection import connect, transaction
from backend.storage.sqlite.sessions import now_iso


def _encode_json(value: dict | list | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _decode_json(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _decode_sources(value: str | None) -> list[dict]:
    decoded = _decode_json(value)
    return decoded if isinstance(decoded, list) else []


def _step_from_row(row: Any) -> AgentStepRecord:
    step = dict(row)
    step["arguments"] = _decode_json(step.pop("arguments_json"))
    step["result"] = _decode_json(step.pop("result_json"))
    step["sources"] = _decode_sources(step.pop("sources_json"))
    return cast(AgentStepRecord, step)


def create_agent_run(
    session_id: str,
    *,
    user_id: str | None = None,
    client_message_id: str | None = None,
    model: str | None = None,
    max_steps: int = 6,
) -> AgentRunRecord:
    if client_message_id is not None:
        existing = get_agent_run_by_client_message_id(client_message_id)
        if existing is not None:
            return existing

    run_id = str(uuid.uuid4())
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
              id, session_id, user_id, client_message_id, status, model, max_steps,
              step_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                run_id,
                session_id,
                user_id,
                client_message_id,
                AgentRunStatus.running,
                model,
                max_steps,
                timestamp,
            ),
        )
    run = get_agent_run(run_id)
    if run is None:
        raise RuntimeError("创建 Agent 运行失败")
    return run


def get_agent_run(run_id: str) -> AgentRunRecord | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
    return cast(AgentRunRecord, dict(row)) if row else None


def get_agent_run_by_client_message_id(client_message_id: str) -> AgentRunRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE client_message_id = ?", (client_message_id,)
        ).fetchone()
    return cast(AgentRunRecord, dict(row)) if row else None


def list_agent_runs(session_id: str, *, limit: int = 50) -> list[AgentRunRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM agent_runs
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [cast(AgentRunRecord, dict(row)) for row in rows]


def finish_agent_run(
    run_id: str,
    status: AgentRunStatus,
    *,
    step_count: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    error_message: str | None = None,
) -> None:
    assignments = ["status = ?", "finished_at = ?"]
    values: list[Any] = [status, now_iso()]
    for column, value in (
        ("step_count", step_count),
        ("prompt_tokens", prompt_tokens),
        ("completion_tokens", completion_tokens),
        ("error_message", error_message),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    values.append(run_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE agent_runs SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )


def create_agent_step(
    run_id: str,
    step_index: int,
    kind: AgentStepKind,
    *,
    tool_name: str | None = None,
    arguments: dict | None = None,
    status: AgentStepStatus = AgentStepStatus.running,
) -> AgentStepRecord:
    step_id = str(uuid.uuid4())
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO agent_steps (
              id, run_id, step_index, kind, tool_name, arguments_json, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                run_id,
                step_index,
                kind,
                tool_name,
                _encode_json(arguments),
                status,
                timestamp,
            ),
        )
    step = get_agent_step(step_id)
    if step is None:
        raise RuntimeError("创建 Agent 步骤失败")
    return step


def get_agent_step(step_id: str) -> AgentStepRecord | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM agent_steps WHERE id = ?", (step_id,)).fetchone()
    return _step_from_row(row) if row else None


def finish_agent_step(
    step_id: str,
    status: AgentStepStatus,
    *,
    result: dict | None = None,
    sources: list[dict] | None = None,
    summary: str | None = None,
    error_message: str | None = None,
    latency_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> None:
    assignments = ["status = ?"]
    values: list[Any] = [status]
    for column, value in (
        ("result_json", _encode_json(result)),
        ("sources_json", _encode_json(sources)),
        ("summary", summary),
        ("error_message", error_message),
        ("latency_ms", latency_ms),
        ("prompt_tokens", prompt_tokens),
        ("completion_tokens", completion_tokens),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    values.append(step_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE agent_steps SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )


def list_agent_steps(run_id: str) -> list[AgentStepRecord]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_index ASC",
            (run_id,),
        ).fetchall()
    return [_step_from_row(row) for row in rows]
