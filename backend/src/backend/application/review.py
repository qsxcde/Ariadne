"""Deterministic weekly reading review."""

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import weekly as weekly_repo
from backend.storage.sqlite.connection import connect


def current_week_start(days: int = 7) -> str:
    return (datetime.now(UTC).date() - timedelta(days=days - 1)).isoformat()


def weekly_review(user_id: str | None, days: int = 7) -> dict[str, Any]:
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    papers = paper_repo.list_papers(user_id, limit=1000)
    read_papers = [
        paper
        for paper in papers
        if paper["reading_status"] == "read"
        and paper["last_read_at"]
        and paper["last_read_at"] >= cutoff
    ]
    reading_papers = [
        paper for paper in papers if paper["reading_status"] == "reading"
    ]
    queued_papers = [
        paper
        for paper in papers
        if paper["reading_status"] in {"inbox", "queued"}
    ]

    paper_ids = [paper["id"] for paper in papers]
    notes = 0
    open_questions = 0
    if paper_ids:
        placeholders = ", ".join("?" for _ in paper_ids)
        with connect() as conn:
            rows = conn.execute(
                f"""
                SELECT type, COUNT(*) AS total
                FROM annotations
                WHERE paper_id IN ({placeholders}) AND created_at >= ?
                GROUP BY type
                """,
                (*paper_ids, cutoff),
            ).fetchall()
        counts = {str(row["type"]): int(row["total"]) for row in rows}
        notes = counts.get("note", 0) + counts.get("highlight", 0)
        open_questions = counts.get("question", 0)

    week_start = current_week_start(days)
    return {
        "week_start": week_start,
        "read_papers": len(read_papers),
        "reading_papers": len(reading_papers),
        "queued_papers": len(queued_papers),
        "notes": notes,
        "open_questions": open_questions,
        "read_paper_ids": [paper["id"] for paper in read_papers],
        "note": weekly_repo.get_note(user_id, week_start),
    }


def save_weekly_note(user_id: str | None, note: str, days: int = 7) -> dict[str, Any]:
    weekly_repo.save_note(user_id, current_week_start(days), note.strip())
    return weekly_review(user_id, days)
