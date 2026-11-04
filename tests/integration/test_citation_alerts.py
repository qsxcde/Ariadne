"""Citation-change alerts for tracked papers."""

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application.follow import citation_alerts
from backend.application.follow import notifications as notification_service
from backend.main import app
from backend.storage.sqlite import alerts as alert_repo
from backend.storage.sqlite import papers as paper_repo


def _paper(title: str = "Paper") -> str:
    return paper_repo.create_paper(
        user_id="u1", title=title, arxiv_id="2401.00001"
    )["id"]


@pytest.mark.integration
def test_first_check_records_baseline_without_notifying(monkeypatch):
    paper_id = _paper()
    monkeypatch.setattr(
        citation_alerts, "get_citation_graph", lambda *_: {"cited_by_count": 5}
    )

    result = citation_alerts.check_citation_updates("u1")

    assert result["checked"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 0
    assert paper_repo.get_paper(paper_id)["last_citation_count"] == 5
    assert notification_service.list_notifications("u1") == []


@pytest.mark.integration
def test_increase_notifies_once_when_enabled(monkeypatch):
    _paper()
    counts = {"value": 5}
    monkeypatch.setattr(
        citation_alerts,
        "get_citation_graph",
        lambda *_: {"cited_by_count": counts["value"]},
    )
    citation_alerts.check_citation_updates("u1")
    alert_repo.update("u1", new_citation=1)

    counts["value"] = 9
    second = citation_alerts.check_citation_updates("u1")
    assert second["notified"] == 1
    notes = notification_service.list_notifications("u1")
    assert [note["kind"] for note in notes] == ["citation"]
    assert "5 → 9" in notes[0]["body"]

    third = citation_alerts.check_citation_updates("u1")
    assert third["notified"] == 0
    assert len(notification_service.list_notifications("u1")) == 1


@pytest.mark.integration
def test_muted_citation_alert_still_updates_baseline(monkeypatch):
    paper_id = _paper()
    counts = {"value": 5}
    monkeypatch.setattr(
        citation_alerts,
        "get_citation_graph",
        lambda *_: {"cited_by_count": counts["value"]},
    )
    citation_alerts.check_citation_updates("u1")
    alert_repo.update("u1", new_citation=0)

    counts["value"] = 7
    result = citation_alerts.check_citation_updates("u1")

    assert result["notified"] == 0
    assert paper_repo.get_paper(paper_id)["last_citation_count"] == 7


@pytest.mark.integration
def test_unindexed_paper_is_reported_not_fatal(monkeypatch):
    _paper()

    def boom(*_args):
        raise ValueError("OpenAlex work not found")

    monkeypatch.setattr(citation_alerts, "get_citation_graph", boom)
    result = citation_alerts.check_citation_updates("u1")

    assert result["checked"] == 0
    assert result["errors"] and "OpenAlex" in result["errors"][0]


@pytest.mark.integration
def test_citation_check_api(monkeypatch):
    _paper()
    monkeypatch.setattr(
        citation_alerts, "get_citation_graph", lambda *_: {"cited_by_count": 3}
    )
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "alice",
    }
    client = TestClient(app)
    try:
        response = client.post("/notifications/check-citations")
        assert response.status_code == 200, response.text
        assert response.json()["checked"] == 1
    finally:
        app.dependency_overrides.clear()
