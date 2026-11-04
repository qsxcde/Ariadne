"""Collections, collection membership and paper tags."""

import uuid
from typing import cast

from backend.storage.records import CollectionRecord, PaperRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso


def create_collection(
    *,
    user_id: str | None,
    name: str,
    description: str | None = None,
    collection_id: str | None = None,
) -> CollectionRecord:
    resolved_id = collection_id or str(uuid.uuid4())
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO collections (
              id, user_id, name, description, sort_order, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (resolved_id, user_id, name, description, timestamp, timestamp),
        )
    collection = get_collection(resolved_id)
    if collection is None:
        raise RuntimeError("创建集合失败")
    return collection


def get_collection(collection_id: str) -> CollectionRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM collections WHERE id = ?", (collection_id,)
        ).fetchone()
        return cast(CollectionRecord | None, row_to_dict(row))


def list_collections(user_id: str | None) -> list[CollectionRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM collections
            WHERE user_id IS ?
            ORDER BY sort_order ASC, updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [cast(CollectionRecord, dict(row)) for row in rows]


def update_collection(
    collection_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
) -> CollectionRecord | None:
    assignments: list[str] = []
    values: list[object] = []
    for column, value in (
        ("name", name),
        ("description", description),
        ("sort_order", sort_order),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if not assignments:
        return get_collection(collection_id)
    assignments.append("updated_at = ?")
    values.extend([now_iso(), collection_id])
    with transaction() as conn:
        conn.execute(
            f"UPDATE collections SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )
    return get_collection(collection_id)


def add_paper_to_collection(
    collection_id: str, paper_id: str, *, sort_order: int = 0
) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO collection_papers (
              collection_id, paper_id, added_at, sort_order
            )
            VALUES (?, ?, ?, ?)
            """,
            (collection_id, paper_id, now_iso(), sort_order),
        )


def remove_paper_from_collection(collection_id: str, paper_id: str) -> None:
    with transaction() as conn:
        conn.execute(
            "DELETE FROM collection_papers WHERE collection_id = ? AND paper_id = ?",
            (collection_id, paper_id),
        )


def list_collection_papers(collection_id: str) -> list[PaperRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.*
            FROM papers p
            JOIN collection_papers cp ON cp.paper_id = p.id
            WHERE cp.collection_id = ?
            ORDER BY cp.sort_order ASC, cp.added_at ASC
            """,
            (collection_id,),
        ).fetchall()
    return [cast(PaperRecord, dict(row)) for row in rows]


def list_collections_for_paper(paper_id: str) -> list[CollectionRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*
            FROM collections c
            JOIN collection_papers cp ON cp.collection_id = c.id
            WHERE cp.paper_id = ?
            ORDER BY c.sort_order ASC, c.updated_at DESC
            """,
            (paper_id,),
        ).fetchall()
    return [cast(CollectionRecord, dict(row)) for row in rows]


def list_tags(paper_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT tag FROM paper_tags WHERE paper_id = ? ORDER BY tag ASC",
            (paper_id,),
        ).fetchall()
    return [str(row["tag"]) for row in rows]
