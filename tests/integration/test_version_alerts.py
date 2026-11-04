"""arXiv version-change alerts."""

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application.follow import notifications as notification_service
from backend.application.follow import version_alerts
from backend.main import app
from backend.storage.sqlite import alerts as alert_repo
from backend.storage.sqlite import papers as paper_repo


def _paper(title: str = "Paper") -> str:
    return paper_repo.create_paper(
        user_id="u1", title=title, arxiv_id="2401.00001"
    )["id"]


@pytest.mark.integration
def test_first_version_check_records_baseline(monkeypatch):
    paper_id = _paper()
    monkeypatch.setattr(
        version_alerts, "fetch_arxiv_updated", lambda *_: "2026-11-01T00:00:00Z"
    )

    result = version_alerts.check_version_updates("u1")

    assert result["checked"] == 1
    assert result["updated"] == 1
    assert result["notified"] == 0
    assert paper_repo.get_paper(paper_id)["last_arxiv_updated"] == "2026-11-01T00:00:00Z"
    assert notification_service.list_notifications("u1") == []


@pytest.mark.integration
def test_newer_version_notifies_once(monkeypatch):
    _paper()
    stamps = {"value": "2026-11-01T00:00:00Z"}
    monkeypatch.setattr(
        version_alerts, "fetch_arxiv_updated", lambda *_: stamps["value"]
    )
    version_alerts.check_version_updates("u1")
    alert_repo.update("u1", new_version=1)

    stamps["value"] = "2026-11-03T00:00:00Z"
    second = version_alerts.check_version_updates("u1")
    assert second["notified"] == 1
    notes = notification_service.list_notifications("u1")
    assert [note["kind"] for note in notes] == ["version"]
    assert "2026-11-01T00:00:00Z → 2026-11-03T00:00:00Z" in notes[0]["body"]

    third = version_alerts.check_version_updates("u1")
    assert third["notified"] == 0


@pytest.mark.integration
def test_muted_version_alert_still_updates_baseline(monkeypatch):
    _paper()
    stamps = {"value": "2026-11-01T00:00:00Z"}
    monkeypatch.setattr(
        version_alerts, "fetch_arxiv_updated", lambda *_: stamps["value"]
    )
    version_alerts.check_version_updates("u1")
    alert_repo.update("u1", new_version=0)

    stamps["value"] = "2026-11-05T00:00:00Z"
    result = version_alerts.check_version_updates("u1")

    assert result["notified"] == 0
    assert notification_service.list_notifications("u1") == []


@pytest.mark.integration
def test_arxiv_error_is_reported(monkeypatch):
    _paper()

    def boom(*_args):
        raise RuntimeError("arxiv down")

    monkeypatch.setattr(version_alerts, "fetch_arxiv_updated", boom)
    result = version_alerts.check_version_updates("u1")

    assert result["checked"] == 0
    assert result["errors"] and "arxiv down" in result["errors"][0]


@pytest.mark.integration
def test_version_check_api(monkeypatch):
    _paper()
    monkeypatch.setattr(
        version_alerts, "fetch_arxiv_updated", lambda *_: "2026-11-01T00:00:00Z"
    )
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "alice",
    }
    client = TestClient(app)
    try:
        response = client.post("/notifications/check-versions")
        assert response.status_code == 200, response.text
        assert response.json()["checked"] == 1
    finally:
        app.dependency_overrides.clear()
