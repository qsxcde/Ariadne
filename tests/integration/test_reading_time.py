"""Reading time log, dashboard aggregation and API."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application.reading import progress as reading_service
from backend.domain.exceptions import PaperNotFoundError
from backend.main import app
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import reading as reading_repo


def _paper(user_id: str = "u1", title: str = "Paper") -> str:
    return paper_repo.create_paper(user_id=user_id, title=title)["id"]


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
def test_record_reading_accumulates_paper_total_and_days():
    paper_id = _paper()
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)

    assert reading_repo.record_reading("u1", paper_id, 120) == 120
    assert reading_repo.record_reading("u1", paper_id, 60, day=yesterday.isoformat()) == 60
    assert reading_repo.record_reading("u1", paper_id, 0) == 0

    paper = paper_repo.get_paper(paper_id)
    assert paper is not None
    assert paper["time_spent_seconds"] == 180

    summary = reading_repo.summarize("u1", days=7)
    assert summary["today_seconds"] == 120
    assert summary["week_seconds"] == 180
    assert summary["total_seconds"] == 180
    assert [row["day"] for row in summary["by_day"]] == [
        yesterday.isoformat(),
        today.isoformat(),
    ]
    assert summary["by_paper"] == [
        {"paper_id": paper_id, "title": "Paper", "seconds": 180}
    ]


@pytest.mark.integration
def test_summary_is_scoped_by_user_and_window():
    mine = _paper("u1", "Mine")
    other = _paper("u2", "Other")
    reading_repo.record_reading("u1", mine, 30)
    reading_repo.record_reading("u2", other, 90)

    assert reading_repo.summarize("u1")["total_seconds"] == 30
    assert reading_repo.summarize("u2")["total_seconds"] == 90
    assert reading_repo.summarize("u1", days=1)["total_seconds"] == 30

    old_day = (datetime.now(UTC).date() - timedelta(days=30)).isoformat()
    reading_repo.record_reading("u1", mine, 45, day=old_day)
    assert reading_repo.summarize("u1", days=7)["total_seconds"] == 30
    assert reading_repo.summarize("u1", days=60)["total_seconds"] == 75


@pytest.mark.integration
def test_reading_time_rejects_other_users_paper():
    paper_id = _paper("u2")
    with pytest.raises(PaperNotFoundError):
        reading_service.record_reading_time(paper_id, "u1", 30)


@pytest.mark.integration
def test_reading_time_api_and_library_stats(client: TestClient):
    paper_id = _paper()

    recorded = client.post(f"/papers/{paper_id}/reading-time", json={"seconds": 90})
    assert recorded.status_code == 201, recorded.text
    body = recorded.json()
    assert body["paper_id"] == paper_id
    assert body["added_seconds"] == 90
    assert body["total_seconds"] == 90

    stats = client.get("/papers/reading-stats?days=7")
    assert stats.status_code == 200
    payload = stats.json()
    assert payload["today_seconds"] == 90
    assert payload["week_seconds"] == 90
    assert payload["by_paper"][0]["seconds"] == 90

    library = client.get("/papers/stats")
    assert library.status_code == 200
    assert library.json()["reading_seconds_today"] == 90
    assert library.json()["reading_seconds_week"] == 90

    invalid = client.post(f"/papers/{paper_id}/reading-time", json={"seconds": 0})
    assert invalid.status_code == 422

    missing = client.post("/papers/unknown/reading-time", json={"seconds": 30})
    assert missing.status_code == 404
