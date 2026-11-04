"""Feed subscriptions, refresh, save and ignore."""

import json

import pytest

from backend.application.follow.feed import (
    FakeFeedSource,
    create_subscription,
    ignore_feed_item,
    list_feed,
    list_subscriptions,
    refresh_feed,
    save_feed_item,
)
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import subscriptions as subscription_repo


def _source() -> FakeFeedSource:
    return FakeFeedSource(
        [
            {
                "external_id": "arxiv-1",
                "title": "A New Paper",
                "authors_json": json.dumps(["Alice"], ensure_ascii=False),
                "abstract": "Abstract text",
                "url": "https://arxiv.org/abs/1",
                "published_at": "2026-11-01T00:00:00+00:00",
            }
        ]
    )


@pytest.mark.integration
def test_subscriptions_are_idempotent_and_user_scoped():
    first = create_subscription("u1", kind="keyword", value="RAG")
    second = create_subscription("u1", kind="keyword", value="RAG")
    assert first["id"] == second["id"]
    assert [row["value"] for row in list_subscriptions("u1")] == ["RAG"]
    assert list_subscriptions("u2") == []
    assert subscription_repo.delete_subscription(first["id"], "u2") is False
    assert subscription_repo.delete_subscription(first["id"], "u1") is True


@pytest.mark.integration
def test_refresh_dedupes_and_save_creates_queued_paper():
    create_subscription("u1", kind="keyword", value="RAG")
    first = refresh_feed("u1", source=_source())
    second = refresh_feed("u1", source=_source())
    assert first["subscriptions"] == 1
    assert second["items"] == 1

    items = list_feed("u1")
    assert len(items) == 1
    assert items[0]["status"] == "new"
    assert items[0]["relevance_reason"] == "匹配订阅：RAG"

    saved = save_feed_item(items[0]["id"], "u1")
    assert saved["status"] == "saved"
    assert saved["paper_id"]
    paper = paper_repo.get_paper(saved["paper_id"])
    assert paper is not None
    assert paper["reading_status"] == "queued"
    assert paper["title"] == "A New Paper"

    ignored = ignore_feed_item(items[0]["id"], "u1")
    assert ignored["status"] == "ignored"
    assert list_feed("u1", status="ignored")[0]["id"] == items[0]["id"]
