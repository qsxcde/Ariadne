"""In-app notifications and optional webhook push."""

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    NotificationDeliverRequest,
    NotificationDeliverResponse,
    NotificationSummary,
)
from backend.api.security import get_current_user
from backend.application import notifications as notification_service

router = APIRouter()


@router.get("/notifications", response_model=list[NotificationSummary])
def list_notifications(
    status: str | None = None, user: dict = Depends(get_current_user)
) -> list[NotificationSummary]:
    return [
        NotificationSummary(**row)
        for row in notification_service.list_notifications(
            user.get("id") or None, status=status
        )
    ]


@router.post("/notifications/{notification_id}/read", response_model=NotificationSummary)
def mark_notification_read(
    notification_id: str, user: dict = Depends(get_current_user)
) -> NotificationSummary:
    row = notification_service.mark_read(
        notification_id, user.get("id") or None
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationSummary(**row)


@router.post("/notifications/deliver", response_model=NotificationDeliverResponse)
def deliver_notifications(
    payload: NotificationDeliverRequest,
    user: dict = Depends(get_current_user),
) -> NotificationDeliverResponse:
    try:
        result = notification_service.deliver_pending(
            user.get("id") or None, webhook_url=payload.webhook_url
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Webhook failed: {exc}") from exc
    return NotificationDeliverResponse(**result)
