"""Read models for agent runs (used by the HTTP replay endpoint)."""

from typing import Any

from backend.storage.sqlite import agent_runs as run_repo
from backend.storage.sqlite import messages as message_repo


def get_agent_run_detail(session_id: str, run_id: str) -> dict[str, Any] | None:
    run = run_repo.get_agent_run(run_id)
    if run is None or run["session_id"] != session_id:
        return None
    message = message_repo.get_message_by_run_id(run_id)
    question = ""
    if run["client_message_id"]:
        user_message = message_repo.get_message_by_client_id(run["client_message_id"])
        question = user_message["content"] if user_message else ""
    return {
        **run,
        "steps": run_repo.list_agent_steps(run_id),
        "answer": message["content"] if message else "",
        "sources": message["sources"] if message else [],
        "question": question,
    }
