"""Feed subscriptions, discovery and save-to-queue."""

import json
from typing import Any, Protocol
from xml.etree import ElementTree

import httpx

from backend.application import notifications as notification_service
from backend.core.model.records import FeedItemRecord, SubscriptionRecord
from backend.storage.sqlite import feed as feed_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import subscriptions as subscription_repo

_ATOM = "{http://www.w3.org/2005/Atom}"


class FeedSource(Protocol):
    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]: ...


class FakeFeedSource:
    """Deterministic source for tests and offline demos."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items

    def fetch(self, _subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        return list(self.items)


class ArxivFeedSource:
    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        field = "au" if subscription["kind"] == "author" else "all"
        query = f"{field}:\"{subscription['value']}\""
        response = httpx.get(
            "https://export.arxiv.org/api/query",
            params={"search_query": query, "start": 0, "max_results": 10},
            timeout=20,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.text)
        items: list[dict[str, Any]] = []
        for entry in root.findall(f"{_ATOM}entry"):
            external_id = (entry.findtext(f"{_ATOM}id") or "").strip()
            title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
            abstract = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
            authors = [
                (author.findtext(f"{_ATOM}name") or "").strip()
                for author in entry.findall(f"{_ATOM}author")
            ]
            link = entry.find(f"{_ATOM}link")
            url = link.get("href") if link is not None else external_id
            published = (entry.findtext(f"{_ATOM}published") or "").strip() or None
            if not external_id or not title:
                continue
            items.append(
                {
                    "external_id": external_id,
                    "title": title,
                    "authors_json": json.dumps(authors, ensure_ascii=False),
                    "abstract": abstract or None,
                    "url": url,
                    "published_at": published,
                }
            )
        return items


def create_subscription(
    user_id: str | None, *, kind: str, value: str
) -> SubscriptionRecord:
    return subscription_repo.create_subscription(
        user_id=user_id, kind=kind, value=value
    )


def list_subscriptions(user_id: str | None) -> list[SubscriptionRecord]:
    return subscription_repo.list_subscriptions(user_id)


def delete_subscription(subscription_id: str, user_id: str | None) -> bool:
    return subscription_repo.delete_subscription(subscription_id, user_id)


def refresh_feed(
    user_id: str | None,
    *,
    source: FeedSource | None = None,
) -> dict[str, int]:
    runner = source or ArxivFeedSource()
    subscriptions = subscription_repo.list_subscriptions(user_id)
    created = 0
    for subscription in subscriptions:
        items = runner.fetch(subscription)
        reason = f"匹配订阅：{subscription['value']}"
        for item in items:
            feed_repo.upsert_feed_item(
                user_id=user_id,
                source="arxiv",
                external_id=str(item["external_id"]),
                title=str(item["title"]),
                authors_json=item.get("authors_json"),
                abstract=item.get("abstract"),
                url=item.get("url"),
                published_at=item.get("published_at"),
                relevance_reason=reason,
            )
            created += 1
        subscription_repo.mark_checked(subscription["id"])
    if created:
        notification_service.create_notification(
            user_id,
            kind="feed",
            title="Feed 有新论文",
            body=f"本次抓取 {created} 条，去 Feed 查看并保存到队列。",
        )
    return {"subscriptions": len(subscriptions), "items": created}


def list_feed(
    user_id: str | None, *, status: str | None = None
) -> list[FeedItemRecord]:
    return feed_repo.list_feed_items(user_id, status=status)


def save_feed_item(item_id: str, user_id: str | None) -> FeedItemRecord:
    item = _accessible_item(item_id, user_id)
    if item["paper_id"]:
        return item
    paper = paper_repo.create_paper(
        user_id=item["user_id"],
        title=item["title"],
        authors_json=item["authors_json"],
        abstract=item["abstract"],
        url=item["url"],
        arxiv_id=item["external_id"] if item["source"] == "arxiv" else None,
    )
    paper_repo.update_reading_state(paper["id"], reading_status="queued")
    updated = feed_repo.set_feed_status(item_id, "saved", paper_id=paper["id"])
    if updated is None:
        raise RuntimeError("保存 feed item 失败")
    return updated


def ignore_feed_item(item_id: str, user_id: str | None) -> FeedItemRecord:
    _accessible_item(item_id, user_id)
    updated = feed_repo.set_feed_status(item_id, "ignored")
    if updated is None:
        raise RuntimeError("忽略 feed item 失败")
    return updated


def _accessible_item(item_id: str, user_id: str | None) -> FeedItemRecord:
    item = feed_repo.get_feed_item(item_id)
    if item is None or item.get("user_id") not in (None, user_id):
        raise ValueError(f"Feed item not found: {item_id}")
    return item
