"""Reading time log used by the dashboard and weekly review."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.storage.sqlite.connection import connect, transaction
from backend.storage.sqlite.sessions import now_iso

_MAX_SECONDS_PER_ENTRY = 24 * 3600


def record_reading(
    user_id: str | None,
    paper_id: str,
    seconds: int,
    *,
    day: str | None = None,
) -> int:
    """Append a reading-time entry and bump the paper's lifetime total."""
    seconds = min(max(int(seconds), 0), _MAX_SECONDS_PER_ENTRY)
    if seconds <= 0:
        return 0
    resolved_day = day or datetime.now(UTC).date().isoformat()
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO reading_log (id, user_id, paper_id, day, seconds, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (f"reading_{uuid.uuid4()}", user_id, paper_id, resolved_day, seconds, timestamp),
        )
        conn.execute(
            "UPDATE papers SET time_spent_seconds = time_spent_seconds + ?, updated_at = ? WHERE id = ?",
            (seconds, timestamp, paper_id),
        )
    return seconds


def summarize(user_id: str | None, days: int = 7) -> dict[str, Any]:
    """Aggregate reading seconds for the last ``days`` days."""
    window = max(1, min(int(days), 365))
    today = datetime.now(UTC).date()
    start = today - timedelta(days=window - 1)
    week_start = today - timedelta(days=6)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT paper_id, day, seconds
            FROM reading_log
            WHERE user_id IS ? AND day >= ?
            """,
            (user_id, start.isoformat()),
        ).fetchall()
        title_rows = conn.execute(
            "SELECT id, title FROM papers WHERE user_id IS ?", (user_id,)
        ).fetchall()

    titles = {str(row["id"]): str(row["title"]) for row in title_rows}
    by_day: dict[str, int] = {}
    by_paper: dict[str, int] = {}
    for row in rows:
        seconds = int(row["seconds"])
        day = str(row["day"])
        by_day[day] = by_day.get(day, 0) + seconds
        paper_id = str(row["paper_id"])
        by_paper[paper_id] = by_paper.get(paper_id, 0) + seconds

    return {
        "days": window,
        "today_seconds": by_day.get(today.isoformat(), 0),
        "week_seconds": sum(
            seconds for day, seconds in by_day.items() if day >= week_start.isoformat()
        ),
        "total_seconds": sum(by_paper.values()),
        "by_day": [
            {"day": day, "seconds": seconds} for day, seconds in sorted(by_day.items())
        ],
        "by_paper": [
            {"paper_id": paper_id, "title": titles.get(paper_id, ""), "seconds": seconds}
            for paper_id, seconds in sorted(by_paper.items(), key=lambda item: -item[1])
        ],
    }
