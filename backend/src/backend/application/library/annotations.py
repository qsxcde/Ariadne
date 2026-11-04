"""Annotation use cases with paper-level access checks."""

import json
from collections.abc import Mapping
from typing import Any

from backend.application.library.papers import get_accessible_paper
from backend.domain.exceptions import AnnotationNotFoundError
from backend.storage.sqlite import annotations as annotation_repo


def list_for_paper(
    paper_id: str, user_id: str | None, *, annotation_type: str | None = None
) -> list[dict[str, Any]]:
    get_accessible_paper(paper_id, user_id)
    return [
        _serialize(row)
        for row in annotation_repo.list_annotations(
            paper_id, annotation_type=annotation_type
        )
    ]


def create_for_paper(
    paper_id: str,
    user_id: str | None,
    *,
    annotation_type: str,
    quote: str | None = None,
    content: str | None = None,
    color: str | None = None,
    document_id: str | None = None,
    chunk_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    bbox: dict[str, float] | None = None,
) -> dict[str, Any]:
    get_accessible_paper(paper_id, user_id)
    row = annotation_repo.create_annotation(
        paper_id=paper_id,
        annotation_type=annotation_type,
        quote=quote,
        content=content,
        color=color,
        document_id=document_id,
        chunk_id=chunk_id,
        page_start=page_start,
        page_end=page_end,
        bbox_json=json.dumps(bbox, ensure_ascii=False) if bbox is not None else None,
    )
    return _serialize(row)


def update_annotation(
    annotation_id: str,
    user_id: str | None,
    *,
    quote: str | None = None,
    content: str | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    row = _get_accessible(annotation_id, user_id)
    updated = annotation_repo.update_annotation(
        row["id"], quote=quote, content=content, color=color
    )
    if updated is None:
        raise AnnotationNotFoundError(
            f"Annotation not found: {annotation_id}", annotation_id=annotation_id
        )
    return _serialize(updated)


def delete_annotation(annotation_id: str, user_id: str | None) -> bool:
    row = _get_accessible(annotation_id, user_id)
    return annotation_repo.delete_annotation(row["id"])


def _get_accessible(annotation_id: str, user_id: str | None) -> dict[str, Any]:
    row = annotation_repo.get_annotation(annotation_id)
    if row is None:
        raise AnnotationNotFoundError(
            f"Annotation not found: {annotation_id}", annotation_id=annotation_id
        )
    get_accessible_paper(row["paper_id"], user_id)
    return dict(row)


def _serialize(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    raw = result.pop("bbox_json", None)
    result["bbox"] = json.loads(raw) if raw else None
    return result
