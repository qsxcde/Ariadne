"""Feed items: discovered papers with new/saved/ignored state."""

import uuid
from typing import cast

from backend.storage.records import FeedItemRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso


def upsert_feed_item(
    *,
    user_id: str | None,
    source: str,
    external_id: str,
    title: str,
    authors_json: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    published_at: str | None = None,
    relevance_reason: str | None = None,
) -> FeedItemRecord:
    item_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO feed_items (
              id, user_id, source, external_id, title, authors_json, abstract,
              url, published_at, paper_id, status, relevance_reason, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'new', ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                item_id,
                user_id,
                source,
                external_id,
                title,
                authors_json,
                abstract,
                url,
                published_at,
                relevance_reason,
                now_iso(),
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM feed_items
            WHERE user_id IS ? AND source = ? AND external_id = ?
            """,
            (user_id, source, external_id),
        ).fetchone()
    if row is None:
        raise RuntimeError("创建 feed item 失败")
    return cast(FeedItemRecord, dict(row))


def get_feed_item(item_id: str) -> FeedItemRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM feed_items WHERE id = ?", (item_id,)
        ).fetchone()
        return cast(FeedItemRecord | None, row_to_dict(row))


def list_feed_items(
    user_id: str | None, *, status: str | None = None, limit: int = 100
) -> list[FeedItemRecord]:
    sql = "SELECT * FROM feed_items WHERE user_id IS ?"
    params: list[object] = [user_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY COALESCE(published_at, created_at) DESC LIMIT ?"
    params.append(max(1, min(limit, 500)))
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [cast(FeedItemRecord, dict(row)) for row in rows]


def set_feed_status(
    item_id: str,
    status: str,
    *,
    paper_id: str | None = None,
) -> FeedItemRecord | None:
    if status not in {"new", "saved", "ignored"}:
        raise ValueError(f"Invalid feed status: {status}")
    with transaction() as conn:
        conn.execute(
            """
            UPDATE feed_items
            SET status = ?, paper_id = COALESCE(?, paper_id)
            WHERE id = ?
            """,
            (status, paper_id, item_id),
        )
    return get_feed_item(item_id)
