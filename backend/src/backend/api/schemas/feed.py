"""Feed and subscription transfer models."""

from typing import Literal

from pydantic import BaseModel, Field

SubscriptionKind = Literal["keyword", "author", "venue", "institution"]
FeedStatus = Literal["new", "saved", "ignored"]


class SubscriptionCreateRequest(BaseModel):
    kind: SubscriptionKind
    value: str


class SubscriptionSummary(BaseModel):
    id: str
    kind: SubscriptionKind
    value: str
    is_active: int
    last_checked_at: str | None = None


class FeedItemSummary(BaseModel):
    id: str
    source: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    url: str | None = None
    published_at: str | None = None
    status: FeedStatus
    paper_id: str | None = None
    relevance_reason: str | None = None
    created_at: str


class FeedRefreshResponse(BaseModel):
    subscriptions: int
    items: int
