"""Annotation endpoints: highlights, notes and questions anchored to a paper."""

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    AnnotationCreateRequest,
    AnnotationSummary,
    AnnotationUpdateRequest,
)
from backend.api.security import get_current_user
from backend.application.library import annotations as annotation_service

router = APIRouter()


@router.get("/papers/{paper_id}/annotations", response_model=list[AnnotationSummary])
def list_annotations(
    paper_id: str,
    type: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[AnnotationSummary]:
    rows = annotation_service.list_for_paper(
        paper_id, user.get("id") or None, annotation_type=type
    )
    return [AnnotationSummary(**row) for row in rows]


@router.post(
    "/papers/{paper_id}/annotations",
    status_code=201,
    response_model=AnnotationSummary,
)
def create_annotation(
    paper_id: str,
    payload: AnnotationCreateRequest,
    user: dict = Depends(get_current_user),
) -> AnnotationSummary:
    try:
        row = annotation_service.create_for_paper(
            paper_id,
            user.get("id") or None,
            annotation_type=payload.type,
            quote=payload.quote,
            content=payload.content,
            color=payload.color,
            document_id=payload.document_id,
            chunk_id=payload.chunk_id,
            page_start=payload.page_start,
            page_end=payload.page_end,
            bbox=payload.bbox,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnnotationSummary(**row)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationSummary)
def update_annotation(
    annotation_id: str,
    payload: AnnotationUpdateRequest,
    user: dict = Depends(get_current_user),
) -> AnnotationSummary:
    try:
        row = annotation_service.update_annotation(
            annotation_id,
            user.get("id") or None,
            quote=payload.quote,
            content=payload.content,
            color=payload.color,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnnotationSummary(**row)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: str, user: dict = Depends(get_current_user)
) -> dict:
    annotation_service.delete_annotation(annotation_id, user.get("id") or None)
    return {"status": "deleted"}
