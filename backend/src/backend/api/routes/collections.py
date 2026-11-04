"""Collection CRUD and paper membership endpoints."""

from fastapi import APIRouter, Depends

from backend.api.schemas import (
    CollectionCreateRequest,
    CollectionSummary,
    CollectionUpdateRequest,
)
from backend.api.security import get_current_user
from backend.application.library import collections as collection_service

router = APIRouter()


@router.get("/collections", response_model=list[CollectionSummary])
def list_collections(user: dict = Depends(get_current_user)) -> list[CollectionSummary]:
    return [
        CollectionSummary(**row)
        for row in collection_service.list_for_user(user.get("id") or None)
    ]


@router.post("/collections", status_code=201, response_model=CollectionSummary)
def create_collection(
    payload: CollectionCreateRequest,
    user: dict = Depends(get_current_user),
) -> CollectionSummary:
    return CollectionSummary(
        **collection_service.create_collection(
            user.get("id") or None,
            name=payload.name,
            description=payload.description,
        )
    )


@router.patch("/collections/{collection_id}", response_model=CollectionSummary)
def update_collection(
    collection_id: str,
    payload: CollectionUpdateRequest,
    user: dict = Depends(get_current_user),
) -> CollectionSummary:
    return CollectionSummary(
        **collection_service.update_collection(
            collection_id,
            user.get("id") or None,
            name=payload.name,
            description=payload.description,
            sort_order=payload.sort_order,
        )
    )


@router.put("/collections/{collection_id}/papers/{paper_id}")
def add_paper_to_collection(
    collection_id: str,
    paper_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    collection_service.add_paper(
        collection_id, paper_id, user.get("id") or None
    )
    return {"status": "added"}


@router.delete("/collections/{collection_id}/papers/{paper_id}")
def remove_paper_from_collection(
    collection_id: str,
    paper_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    collection_service.remove_paper(
        collection_id, paper_id, user.get("id") or None
    )
    return {"status": "removed"}
