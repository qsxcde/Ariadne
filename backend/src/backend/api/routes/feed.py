"""Feed subscription and discovery endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException

from backend.api.schemas import (
    FeedItemSummary,
    FeedRefreshResponse,
    SubscriptionCreateRequest,
    SubscriptionSummary,
)
from backend.api.security import get_current_user
from backend.application.follow import feed as feed_service

router = APIRouter()


def _authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _item_summary(row: dict) -> FeedItemSummary:
    return FeedItemSummary(
        id=row["id"],
        source=row["source"],
        title=row["title"],
        authors=_authors(row["authors_json"]),
        abstract=row["abstract"],
        url=row["url"],
        published_at=row["published_at"],
        status=row["status"],
        paper_id=row["paper_id"],
        relevance_reason=row["relevance_reason"],
        created_at=row["created_at"],
    )


@router.get("/subscriptions", response_model=list[SubscriptionSummary])
def list_subscriptions(
    user: dict = Depends(get_current_user),
) -> list[SubscriptionSummary]:
    return [
        SubscriptionSummary(**row)
        for row in feed_service.list_subscriptions(user.get("id") or None)
    ]


@router.post(
    "/subscriptions", status_code=201, response_model=SubscriptionSummary
)
def create_subscription(
    payload: SubscriptionCreateRequest,
    user: dict = Depends(get_current_user),
) -> SubscriptionSummary:
    try:
        row = feed_service.create_subscription(
            user.get("id") or None,
            kind=payload.kind,
            value=payload.value,
            source=payload.source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SubscriptionSummary(**row)


@router.delete("/subscriptions/{subscription_id}")
def delete_subscription(
    subscription_id: str, user: dict = Depends(get_current_user)
) -> dict:
    deleted = feed_service.delete_subscription(
        subscription_id, user.get("id") or None
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"status": "deleted"}


@router.get("/feed", response_model=list[FeedItemSummary])
def list_feed(
    status: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[FeedItemSummary]:
    return [
        _item_summary(row)
        for row in feed_service.list_feed(user.get("id") or None, status=status)
    ]


@router.post("/feed/refresh", response_model=FeedRefreshResponse)
def refresh_feed(user: dict = Depends(get_current_user)) -> FeedRefreshResponse:
    try:
        result = feed_service.refresh_feed(user.get("id") or None)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Feed source failed: {exc}") from exc
    return FeedRefreshResponse(**result)


@router.post("/feed/{item_id}/save", response_model=FeedItemSummary)
def save_feed_item(
    item_id: str, user: dict = Depends(get_current_user)
) -> FeedItemSummary:
    try:
        row = feed_service.save_feed_item(item_id, user.get("id") or None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _item_summary(row)


@router.post("/feed/{item_id}/ignore", response_model=FeedItemSummary)
def ignore_feed_item(
    item_id: str, user: dict = Depends(get_current_user)
) -> FeedItemSummary:
    try:
        row = feed_service.ignore_feed_item(item_id, user.get("id") or None)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _item_summary(row)
