"""Token-based Zotero / Notion export endpoints."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    IntegrationExportResponse,
    NotionExportRequest,
    ZoteroExportRequest,
)
from backend.api.security import get_current_user
from backend.application.library import integrations as integration_service

router = APIRouter()


@router.post("/integrations/zotero/export", response_model=IntegrationExportResponse)
def export_zotero(
    payload: ZoteroExportRequest,
    user: dict = Depends(get_current_user),
) -> IntegrationExportResponse:
    try:
        result = integration_service.export_to_zotero(
            user.get("id") or None,
            api_key=payload.api_key,
            library_id=payload.library_id,
            library_type=payload.library_type,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Zotero failed: {exc}") from exc
    return IntegrationExportResponse(**result)


@router.post("/integrations/notion/export", response_model=IntegrationExportResponse)
def export_notion(
    payload: NotionExportRequest,
    user: dict = Depends(get_current_user),
) -> IntegrationExportResponse:
    try:
        result = integration_service.export_to_notion(
            user.get("id") or None,
            token=payload.token,
            database_id=payload.database_id,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Notion failed: {exc}") from exc
    return IntegrationExportResponse(**result)
