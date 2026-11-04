"""Reading annotations: highlights, notes and open questions."""

import uuid
from typing import cast

from backend.storage.records import AnnotationRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso

_ANNOTATION_TYPES = {"highlight", "note", "question"}


def _validate_anchor(
    conn,
    *,
    paper_id: str,
    document_id: str | None,
    chunk_id: str | None,
) -> str | None:
    resolved_document_id = document_id
    if chunk_id:
        row = conn.execute(
            "SELECT paper_id, document_id FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if row is None or row["paper_id"] != paper_id:
            raise ValueError("Chunk does not belong to this paper")
        if document_id and document_id != row["document_id"]:
            raise ValueError("Chunk does not belong to this document")
        resolved_document_id = str(row["document_id"])
    elif document_id:
        row = conn.execute(
            "SELECT paper_id FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        if row is None or row["paper_id"] != paper_id:
            raise ValueError("Document does not belong to this paper")
    return resolved_document_id


def create_annotation(
    *,
    paper_id: str,
    annotation_type: str,
    quote: str | None = None,
    content: str | None = None,
    color: str | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    bbox_json: str | None = None,
) -> AnnotationRecord:
    if annotation_type not in _ANNOTATION_TYPES:
        raise ValueError(f"Invalid annotation type: {annotation_type}")
    if annotation_type == "highlight" and not (quote or "").strip():
        raise ValueError("Highlight requires quote")
    if annotation_type in {"note", "question"} and not (content or "").strip():
        raise ValueError(f"{annotation_type} requires content")

    annotation_id = str(uuid.uuid4())
    timestamp = now_iso()
    with transaction() as conn:
        resolved_document_id = _validate_anchor(
            conn,
            paper_id=paper_id,
            document_id=document_id,
            chunk_id=chunk_id,
        )
        conn.execute(
            """
            INSERT INTO annotations (
              id, paper_id, document_id, chunk_id, type, quote, content, color,
              page_start, page_end, bbox_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                annotation_id,
                paper_id,
                resolved_document_id,
                chunk_id,
                annotation_type,
                quote,
                content,
                color,
                page_start,
                page_end,
                bbox_json,
                timestamp,
                timestamp,
            ),
        )
    annotation = get_annotation(annotation_id)
    if annotation is None:
        raise RuntimeError("创建批注失败")
    return annotation


def get_annotation(annotation_id: str) -> AnnotationRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
        ).fetchone()
        return cast(AnnotationRecord | None, row_to_dict(row))


def list_annotations(
    paper_id: str, *, annotation_type: str | None = None
) -> list[AnnotationRecord]:
    sql = "SELECT * FROM annotations WHERE paper_id = ?"
    params: list[object] = [paper_id]
    if annotation_type:
        sql += " AND type = ?"
        params.append(annotation_type)
    sql += " ORDER BY created_at ASC"
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [cast(AnnotationRecord, dict(row)) for row in rows]


def update_annotation(
    annotation_id: str,
    *,
    quote: str | None = None,
    content: str | None = None,
    color: str | None = None,
) -> AnnotationRecord | None:
    assignments: list[str] = []
    values: list[object] = []
    for column, value in (
        ("quote", quote),
        ("content", content),
        ("color", color),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if not assignments:
        return get_annotation(annotation_id)
    assignments.append("updated_at = ?")
    values.extend([now_iso(), annotation_id])
    with transaction() as conn:
        conn.execute(
            f"UPDATE annotations SET {', '.join(assignments)} WHERE id = ?",
            tuple(values),
        )
    return get_annotation(annotation_id)


def delete_annotation(annotation_id: str) -> bool:
    with transaction() as conn:
        cursor = conn.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
    return cursor.rowcount > 0


def count_by_type_for_papers(
    paper_ids: list[str], *, since: str | None = None
) -> dict[str, int]:
    """Aggregate annotation counts for a set of papers, optionally since a time."""
    if not paper_ids:
        return {}
    placeholders = ", ".join("?" for _ in paper_ids)
    sql = (
        f"SELECT type, COUNT(*) AS total FROM annotations "
        f"WHERE paper_id IN ({placeholders})"
    )
    params: list[object] = list(paper_ids)
    if since is not None:
        sql += " AND created_at >= ?"
        params.append(since)
    sql += " GROUP BY type"
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return {str(row["type"]): int(row["total"]) for row in rows}
