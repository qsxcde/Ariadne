"""Feed subscriptions, discovery and save-to-queue."""

import json
import time
from typing import Any, Protocol
from xml.etree import ElementTree

import httpx

from backend.application import notifications as notification_service
from backend.core.model.records import FeedItemRecord, SubscriptionRecord
from backend.storage.sqlite import feed as feed_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import subscriptions as subscription_repo

_ATOM = "{http://www.w3.org/2005/Atom}"
_MAX_ATTEMPTS = 3


class FeedSource(Protocol):
    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]: ...


class FakeFeedSource:
    """Deterministic source for tests and offline demos."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items

    def fetch(self, _subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        return list(self.items)


def _get(
    url: str, *, params: dict[str, Any] | None = None, timeout: float = 20
) -> httpx.Response:
    """GET with bounded retries; every adapter shares the same backoff policy."""
    last_error: httpx.HTTPError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": "SciPal/0.1 (feed)"},
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(0.5 * (2**attempt))
    assert last_error is not None
    raise last_error


def _clean(value: str | None) -> str:
    return " ".join((value or "").split())


def _atom_items(root: ElementTree.Element) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for entry in root.findall(f"{_ATOM}entry"):
        external_id = (entry.findtext(f"{_ATOM}id") or "").strip()
        title = _clean(entry.findtext(f"{_ATOM}title"))
        abstract = _clean(entry.findtext(f"{_ATOM}summary"))
        authors = [
            _clean(author.findtext(f"{_ATOM}name"))
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
                "authors_json": json.dumps([a for a in authors if a], ensure_ascii=False),
                "abstract": abstract or None,
                "url": url,
                "published_at": published,
            }
        )
    return items


class ArxivFeedSource:
    name = "arxiv"

    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        field = "au" if subscription["kind"] == "author" else "all"
        query = f"{field}:\"{subscription['value']}\""
        response = _get(
            "https://export.arxiv.org/api/query",
            params={"search_query": query, "start": 0, "max_results": 10},
        )
        return _atom_items(ElementTree.fromstring(response.text))


def _openalex_abstract(index: Any) -> str | None:
    if not isinstance(index, dict):
        return None
    pairs: list[tuple[int, str]] = []
    for word, positions in index.items():
        if isinstance(positions, list):
            pairs.extend((int(position), str(word)) for position in positions)
    if not pairs:
        return None
    return " ".join(word for _, word in sorted(pairs))


class OpenAlexFeedSource:
    name = "openalex"

    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        response = _get(
            "https://api.openalex.org/works",
            params={
                "search": subscription["value"],
                "per-page": 10,
                "sort": "publication_date:desc",
            },
        )
        payload = response.json()
        items: list[dict[str, Any]] = []
        for work in payload.get("results") or []:
            title = _clean(work.get("title"))
            external_id = str(work.get("id") or "")
            if not title or not external_id:
                continue
            authors = [
                str((authorship.get("author") or {}).get("display_name") or "")
                for authorship in work.get("authorships") or []
            ]
            items.append(
                {
                    "external_id": external_id,
                    "title": title,
                    "authors_json": json.dumps(
                        [a for a in authors if a], ensure_ascii=False
                    ),
                    "abstract": _openalex_abstract(work.get("abstract_inverted_index")),
                    "url": str(work.get("doi") or external_id),
                    "published_at": work.get("publication_date"),
                }
            )
        return items


class PubMedFeedSource:
    name = "pubmed"

    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        search = _get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params={
                "db": "pubmed",
                "term": subscription["value"],
                "retmode": "json",
                "retmax": 10,
                "sort": "date",
            },
        ).json()
        ids = (search.get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return []
        summary = _get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        ).json()
        result = summary.get("result") or {}
        items: list[dict[str, Any]] = []
        for uid in ids:
            row = result.get(str(uid)) or {}
            title = _clean(row.get("title"))
            if not title:
                continue
            authors = [str(a.get("name") or "") for a in row.get("authors") or []]
            items.append(
                {
                    "external_id": f"pubmed:{uid}",
                    "title": title,
                    "authors_json": json.dumps(
                        [a for a in authors if a], ensure_ascii=False
                    ),
                    "abstract": None,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                    "published_at": row.get("pubdate"),
                }
            )
        return items


class RssFeedSource:
    name = "rss"

    def fetch(self, subscription: SubscriptionRecord) -> list[dict[str, Any]]:
        url = subscription["value"].strip()
        if not url.lower().startswith(("http://", "https://")):
            raise ValueError("RSS 订阅需要 http(s) 链接")
        response = _get(url)
        root = ElementTree.fromstring(response.content)
        items = _atom_items(root)
        if items:
            return items
        for item in root.iter("item"):
            title = _clean(item.findtext("title"))
            if not title:
                continue
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or "").strip()
            author = _clean(item.findtext("author"))
            published = (item.findtext("pubDate") or "").strip() or None
            items.append(
                {
                    "external_id": guid or link or title,
                    "title": title,
                    "authors_json": json.dumps([author], ensure_ascii=False) if author else None,
                    "abstract": _clean(item.findtext("description")) or None,
                    "url": link or None,
                    "published_at": published,
                }
            )
        return items


_SOURCES: dict[str, FeedSource] = {
    "arxiv": ArxivFeedSource(),
    "openalex": OpenAlexFeedSource(),
    "pubmed": PubMedFeedSource(),
    "rss": RssFeedSource(),
}


def create_subscription(
    user_id: str | None, *, kind: str, value: str, source: str = "arxiv"
) -> SubscriptionRecord:
    return subscription_repo.create_subscription(
        user_id=user_id, kind=kind, value=value, source=source
    )


def list_subscriptions(user_id: str | None) -> list[SubscriptionRecord]:
    return subscription_repo.list_subscriptions(user_id)


def delete_subscription(subscription_id: str, user_id: str | None) -> bool:
    return subscription_repo.delete_subscription(subscription_id, user_id)


def refresh_feed(
    user_id: str | None,
    *,
    source: FeedSource | None = None,
) -> dict[str, Any]:
    subscriptions = subscription_repo.list_subscriptions(user_id)
    created = 0
    errors: list[str] = []
    for subscription in subscriptions:
        source_name = str(subscription.get("source") or "arxiv")
        runner = source or _SOURCES.get(source_name)
        if runner is None:
            errors.append(f"{subscription['value']}: 未知来源 {source_name}")
            continue
        try:
            items = runner.fetch(subscription)
        except Exception as exc:  # 单个订阅失败不影响其它订阅
            errors.append(f"{subscription['value']}: {exc}")
            continue
        reason = f"匹配订阅：{subscription['value']}"
        for item in items:
            feed_repo.upsert_feed_item(
                user_id=user_id,
                source=source_name,
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
    return {
        "subscriptions": len(subscriptions),
        "items": created,
        "errors": errors,
    }


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
