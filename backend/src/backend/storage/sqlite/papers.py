"""Paper repository: the library-level asset that owns reading state."""

import uuid
from typing import cast

from backend.core.model.records import PaperRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso

_READING_STATUSES = {"inbox", "queued", "skimming", "reading", "read", "archived"}


def get_paper(paper_id: str) -> PaperRecord | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]


def create_paper(
    *,
    user_id: str | None,
    title: str,
    paper_id: str | None = None,
    authors_json: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    metadata_json: str | None = None,
) -> PaperRecord:
    resolved_id = paper_id or f"paper_{uuid.uuid4()}"
    timestamp = now_iso()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO papers (
              id, user_id, title, authors_json, year, venue, doi, arxiv_id,
              abstract, url, metadata_json, reading_status, progress,
              last_location_json, last_read_at, time_spent_seconds,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'inbox', 0, NULL, NULL, 0, ?, ?)
            """,
            (
                resolved_id,
                user_id,
                title,
                authors_json,
                year,
                venue,
                doi,
                arxiv_id,
                abstract,
                url,
                metadata_json,
                timestamp,
                timestamp,
            ),
        )
    paper = get_paper(resolved_id)
    if paper is None:
        raise RuntimeError("创建论文失败")
    return paper


def ensure_paper_for_session(
    session_id: str,
    title: str,
    *,
    paper_id: str | None = None,
) -> str:
    """Return the session's paper, creating one when the session is still empty.

    This is a compatibility bridge for the v8 migration window: old call sites
    only know a session id, while the paper is the new library-level owner.
    """
    with transaction() as conn:
        session = conn.execute(
            "SELECT paper_id, user_id FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None:
            raise RuntimeError(f"Session not found: {session_id}")
        existing = session["paper_id"]
        if existing:
            return str(existing)

        resolved_id = paper_id or f"paper_{uuid.uuid4()}"
        timestamp = now_iso()
        conn.execute(
            """
            INSERT INTO papers (
              id, user_id, title, reading_status, progress,
              last_location_json, last_read_at, time_spent_seconds,
              created_at, updated_at
            )
            VALUES (?, ?, ?, 'inbox', 0, NULL, NULL, 0, ?, ?)
            """,
            (resolved_id, session["user_id"], title, timestamp, timestamp),
        )
        conn.execute(
            "UPDATE sessions SET paper_id = ?, updated_at = ? WHERE id = ?",
            (resolved_id, timestamp, session_id),
        )
        return resolved_id


def update_paper_metadata(
    paper_id: str,
    *,
    title: str | None = None,
    authors_json: str | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
) -> PaperRecord | None:
    assignments: list[str] = []
    values: list[object] = []
    for column, value in (
        ("title", title),
        ("authors_json", authors_json),
        ("year", year),
        ("venue", venue),
        ("doi", doi),
        ("arxiv_id", arxiv_id),
        ("abstract", abstract),
        ("url", url),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if not assignments:
        return get_paper(paper_id)

    assignments.append("updated_at = ?")
    values.extend([now_iso(), paper_id])
    with transaction() as conn:
        conn.execute(
            f"UPDATE papers SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )
    return get_paper(paper_id)


def list_papers(
    user_id: str | None,
    *,
    reading_status: str | None = None,
    collection_id: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    limit: int = 200,
) -> list[PaperRecord]:
    joins: list[str] = []
    where: list[str] = ["p.user_id IS ?"]
    params: list[object] = [user_id]

    if collection_id:
        joins.append("JOIN collection_papers cp ON cp.paper_id = p.id")
        where.append("cp.collection_id = ?")
        params.append(collection_id)
    if tag:
        joins.append("JOIN paper_tags pt ON pt.paper_id = p.id")
        where.append("pt.tag = ?")
        params.append(tag)
    if reading_status:
        where.append("p.reading_status = ?")
        params.append(reading_status)
    if query:
        like = f"%{query.strip()}%"
        where.append("(p.title LIKE ? OR p.authors_json LIKE ?)")
        params.extend([like, like])

    sql = f"""
        SELECT DISTINCT p.*
        FROM papers p
        {' '.join(joins)}
        WHERE {' AND '.join(where)}
        ORDER BY p.updated_at DESC
        LIMIT ?
    """
    params.append(max(1, min(limit, 1000)))
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [cast(PaperRecord, dict(row)) for row in rows]


def find_by_file_hash(user_id: str | None, file_hash: str) -> PaperRecord | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT p.*
            FROM documents d
            JOIN papers p ON p.id = d.paper_id
            WHERE p.user_id IS ? AND d.file_hash = ?
            ORDER BY p.created_at ASC
            LIMIT 1
            """,
            (user_id, file_hash),
        ).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]


def find_by_arxiv_id(user_id: str | None, arxiv_id: str) -> PaperRecord | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM papers
            WHERE user_id IS ? AND arxiv_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (user_id, arxiv_id),
        ).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]


def find_by_doi(user_id: str | None, doi: str) -> PaperRecord | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM papers
            WHERE user_id IS ? AND doi = ? COLLATE NOCASE
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (user_id, doi),
        ).fetchone()
        return row_to_dict(row)  # type: ignore[return-value]


def update_reading_state(
    paper_id: str,
    *,
    reading_status: str | None = None,
    progress: float | None = None,
    last_location_json: str | None = None,
    last_read_at: str | None = None,
    time_spent_seconds: int | None = None,
) -> PaperRecord | None:
    if reading_status is not None and reading_status not in _READING_STATUSES:
        raise ValueError(f"Invalid reading status: {reading_status}")
    if progress is not None:
        progress = min(1.0, max(0.0, float(progress)))

    assignments: list[str] = []
    values: list[object] = []
    for column, value in (
        ("reading_status", reading_status),
        ("progress", progress),
        ("last_location_json", last_location_json),
        ("last_read_at", last_read_at),
        ("time_spent_seconds", time_spent_seconds),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if not assignments:
        return get_paper(paper_id)

    assignments.append("updated_at = ?")
    values.append(now_iso())
    values.append(paper_id)
    with transaction() as conn:
        conn.execute(
            f"UPDATE papers SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )
    return get_paper(paper_id)
