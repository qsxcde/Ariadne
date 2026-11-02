"""Feed and subscription transfer models."""

from typing import Literal

from pydantic import BaseModel, Field

SubscriptionKind = Literal["keyword", "author", "venue", "institution"]
SubscriptionSource = Literal["arxiv", "openalex", "pubmed", "rss"]
FeedStatus = Literal["new", "saved", "ignored"]


class SubscriptionCreateRequest(BaseModel):
    kind: SubscriptionKind
    value: str
    source: SubscriptionSource = "arxiv"


class SubscriptionSummary(BaseModel):
    id: str
    kind: SubscriptionKind
    value: str
    source: SubscriptionSource = "arxiv"
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
    errors: list[str] = Field(default_factory=list)
