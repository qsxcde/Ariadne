"""Editable weekly review notes."""

from backend.storage.sqlite.connection import connect, transaction
from backend.storage.sqlite.sessions import now_iso


def _owner(user_id: str | None) -> str:
    return user_id or ""


def get_note(user_id: str | None, week_start: str) -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT content FROM weekly_reports WHERE user_id = ? AND week_start = ?",
            (_owner(user_id), week_start),
        ).fetchone()
    return str(row["content"]) if row is not None else ""


def save_note(user_id: str | None, week_start: str, content: str) -> None:
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO weekly_reports (user_id, week_start, content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, week_start) DO UPDATE SET
              content = excluded.content,
              updated_at = excluded.updated_at
            """,
            (_owner(user_id), week_start, content, timestamp, timestamp),
        )
