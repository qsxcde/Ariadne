"""Agent run replay endpoint: ownership checks and step payload."""

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.domain.states import AgentRunStatus, AgentStepKind, AgentStepStatus
from backend.main import app
from backend.storage.sqlite import agent_runs
from backend.storage.sqlite import sessions


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "alice",
    }
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_features_expose_agent_flag(client: TestClient, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "agent_enabled", False)
    response = client.get("/features")

    assert response.status_code == 200, response.text
    assert response.json() == {"agent_enabled": False}


@pytest.mark.integration
def test_get_agent_run_returns_steps(client: TestClient):
    session = sessions.create_session("Agent", user_id="u1")
    run = agent_runs.create_agent_run(session["id"], user_id="u1", model="fake")
    step = agent_runs.create_agent_step(
        run["id"],
        1,
        AgentStepKind.tool,
        tool_name="search_session_chunks",
        arguments={"query": "attention"},
    )
    agent_runs.finish_agent_step(
        step["id"],
        AgentStepStatus.ok,
        summary="命中 1 个片段",
        sources=[
            {
                "paper_id": "doc-1",
                "section": "Introduction",
                "chunk_index": 0,
                "text_excerpt": "attention",
            }
        ],
    )
    agent_runs.finish_agent_run(
        run["id"], AgentRunStatus.completed, step_count=1, prompt_tokens=2, completion_tokens=3
    )

    response = client.get(f"/sessions/{session['id']}/runs/{run['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == run["id"]
    assert body["status"] == "completed"
    assert body["step_count"] == 1
    assert body["steps"][0]["tool_name"] == "search_session_chunks"
    assert body["steps"][0]["arguments"] == {"query": "attention"}
    assert body["steps"][0]["sources"][0]["section"] == "Introduction"


@pytest.mark.integration
def test_get_agent_run_rejects_foreign_or_mismatched_session(client: TestClient):
    session = sessions.create_session("Agent", user_id="u1")
    other = sessions.create_session("Other", user_id="u1")
    foreign = sessions.create_session("Foreign", user_id="u2")
    run = agent_runs.create_agent_run(session["id"], user_id="u1")

    assert client.get(f"/sessions/{other['id']}/runs/{run['id']}").status_code == 404
    assert client.get(f"/sessions/{foreign['id']}/runs/{run['id']}").status_code == 404
    assert client.get(f"/sessions/{session['id']}/runs/missing").status_code == 404
