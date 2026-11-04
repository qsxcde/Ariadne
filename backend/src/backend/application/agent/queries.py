"""Read models for agent runs (used by the HTTP replay endpoint)."""

from typing import Any

from backend.storage.sqlite import agent_runs as run_repo


def get_agent_run_detail(session_id: str, run_id: str) -> dict[str, Any] | None:
    run = run_repo.get_agent_run(run_id)
    if run is None or run["session_id"] != session_id:
        return None
    return {**run, "steps": run_repo.list_agent_steps(run_id)}
