"""Local alert preferences and weekly digest."""

from fastapi import APIRouter, Depends

from backend.api.schemas import AlertSettings, AlertSettingsUpdate, DigestResponse
from backend.api.security import get_current_user
from backend.application import alerts as alert_service
from backend.application import feed as feed_service
from backend.application import review as review_service

router = APIRouter()


@router.get("/settings/alerts", response_model=AlertSettings)
def get_alert_settings(user: dict = Depends(get_current_user)) -> AlertSettings:
    return AlertSettings(**alert_service.get_settings(user.get("id") or None))


@router.patch("/settings/alerts", response_model=AlertSettings)
def update_alert_settings(
    payload: AlertSettingsUpdate,
    user: dict = Depends(get_current_user),
) -> AlertSettings:
    fields = payload.model_dump(exclude_unset=True)
    return AlertSettings(
        **alert_service.update_settings(user.get("id") or None, **fields)
    )


@router.get("/digest", response_model=DigestResponse)
def get_digest(user: dict = Depends(get_current_user)) -> DigestResponse:
    user_id = user.get("id") or None
    review = review_service.weekly_review(user_id)
    saved = feed_service.list_feed(user_id, status="saved")
    return DigestResponse(**review, saved_feed_items=len(saved))
