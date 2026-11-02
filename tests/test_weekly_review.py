"""Weekly review counts are deterministic and user-scoped."""

from datetime import UTC, datetime

import pytest

from backend.application.review import weekly_review
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
