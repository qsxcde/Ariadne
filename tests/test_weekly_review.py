"""Weekly review counts are deterministic and user-scoped."""

from datetime import UTC, datetime

import pytest

from backend.application.review import save_weekly_note, weekly_review
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.main import app
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


def _paper(filename: str, user_id: str = "u1") -> str:
    session = session_repo.create_session(filename, user_id=user_id)
    document = document_repo.create_document(
        session_id=session["id"],
        filename=filename,
        file_path=f"/tmp/{filename}",
        mime_type="application/pdf",
        file_size=10,
    )
    return document["paper_id"]


@pytest.mark.integration
def test_weekly_review_counts_read_notes_and_questions():
    read = _paper("read.pdf")
    paper_repo.update_reading_state(
        read,
        reading_status="read",
        last_read_at=datetime.now(UTC).isoformat(),
    )
    annotation_repo.create_annotation(
        paper_id=read, annotation_type="note", content="note"
    )
    annotation_repo.create_annotation(
        paper_id=read, annotation_type="question", content="why?"
    )
    _paper("inbox.pdf")
    _paper("other.pdf", user_id="u2")

    result = weekly_review("u1")

    assert result["read_papers"] == 1
    assert result["queued_papers"] == 1
    assert result["notes"] == 1
    assert result["open_questions"] == 1
    assert result["read_paper_ids"] == [read]


@pytest.mark.integration
def test_weekly_note_is_saved_and_user_scoped():
    assert weekly_review("u1")["note"] == ""
    assert save_weekly_note("u1", "  本周读完两篇  ")["note"] == "本周读完两篇"
    assert weekly_review("u1")["note"] == "本周读完两篇"
    assert weekly_review("u2")["note"] == ""
    assert save_weekly_note("u1", "更新后的复盘")["note"] == "更新后的复盘"
    assert weekly_review("u1")["note"] == "更新后的复盘"


@pytest.mark.integration
def test_weekly_note_api_round_trip():
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "alice"}
    client = TestClient(app)
    try:
        saved = client.put("/review/weekly/note", json={"note": "本周复盘"})
        assert saved.status_code == 200, saved.text
        assert saved.json()["note"] == "本周复盘"

        fetched = client.get("/review/weekly")
        assert fetched.status_code == 200
        assert fetched.json()["note"] == "本周复盘"

        too_long = client.put("/review/weekly/note", json={"note": "x" * 5001})
        assert too_long.status_code == 422
    finally:
        app.dependency_overrides.clear()
