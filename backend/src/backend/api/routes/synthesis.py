"""Cross-paper synthesis endpoints: collection Q&A and comparison."""

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    CollectionAskRequest,
    CollectionAskResponse,
    CollectionCompareRequest,
    PaperComparison,
)
from backend.api.deps import get_text_completer
from backend.api.security import get_current_user
from backend.application.synthesis import service as synthesis_service
from backend.domain.ports import TextCompleter

router = APIRouter()


@router.post(
    "/collections/{collection_id}/ask", response_model=CollectionAskResponse
)
def ask_collection(
    collection_id: str,
    payload: CollectionAskRequest,
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
) -> CollectionAskResponse:
    try:
        result = synthesis_service.answer_collection(
            collection_id,
            user.get("id") or None,
            payload.question,
            completer=completer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CollectionAskResponse(**result)


@router.post(
    "/collections/{collection_id}/compare", response_model=list[PaperComparison]
)
def compare_collection_papers(
    collection_id: str,
    payload: CollectionCompareRequest,
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
) -> list[PaperComparison]:
    try:
        rows = synthesis_service.compare_papers(
            collection_id,
            user.get("id") or None,
            payload.paper_ids,
            completer=completer,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [PaperComparison(**row) for row in rows]
