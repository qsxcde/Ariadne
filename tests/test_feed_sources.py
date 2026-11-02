"""Multi-source feed adapters: OpenAlex, PubMed, RSS and retry."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application import feed
from backend.main import app


class FakeResponse:
    def __init__(self, *, text: str = "", payload=None, content: bytes | None = None):
        self.text = text
        self._payload = payload
        self.content = content if content is not None else text.encode()

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def _subscription(value: str, kind: str = "keyword", source: str = "arxiv"):
    return {"id": "s1", "user_id": "u1", "kind": kind, "value": value, "source": source}


@pytest.mark.unit
def test_openalex_source_maps_works(monkeypatch):
    payload = {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "  A   RAG paper ",
                "doi": "https://doi.org/10.1/x",
                "publication_date": "2026-01-02",
                "authorships": [
                    {"author": {"display_name": "Ada Lovelace"}},
                    {"author": {"display_name": "Alan Turing"}},
                ],
                "abstract_inverted_index": {"Hello": [0], "world": [1]},
            }
        ]
    }
    monkeypatch.setattr(feed, "_get", lambda *a, **k: FakeResponse(payload=payload))

    items = feed.OpenAlexFeedSource().fetch(_subscription("RAG", source="openalex"))

    assert items[0]["external_id"] == "https://openalex.org/W1"
    assert items[0]["title"] == "A RAG paper"
    assert json.loads(items[0]["authors_json"]) == ["Ada Lovelace", "Alan Turing"]
    assert items[0]["abstract"] == "Hello world"
    assert items[0]["url"] == "https://doi.org/10.1/x"


@pytest.mark.unit
def test_pubmed_source_uses_esearch_then_esummary(monkeypatch):
    calls: list[str] = []

    def fake_get(url, *, params=None, timeout=20):
        calls.append(url)
        if "esearch" in url:
            return FakeResponse(payload={"esearchresult": {"idlist": ["123"]}})
        return FakeResponse(
            payload={"result": {"123": {"title": "PubMed paper", "authors": [{"name": "Grace Hopper"}], "pubdate": "2025"}}}
        )

    monkeypatch.setattr(feed, "_get", fake_get)

    items = feed.PubMedFeedSource().fetch(_subscription("cancer", source="pubmed"))

    assert len(calls) == 2
    assert items[0]["external_id"] == "pubmed:123"
    assert items[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert json.loads(items[0]["authors_json"]) == ["Grace Hopper"]


@pytest.mark.unit
def test_rss_source_parses_items(monkeypatch):
    rss = """<?xml version="1.0"?><rss><channel><item><title>Feed post</title><link>https://example.org/p</link><guid>p1</guid><description>Summary</description><pubDate>Mon, 03 Nov 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
    monkeypatch.setattr(feed, "_get", lambda *a, **k: FakeResponse(text=rss, content=rss.encode()))

    items = feed.RssFeedSource().fetch(_subscription("https://example.org/rss", source="rss"))

    assert items[0]["external_id"] == "p1"
    assert items[0]["title"] == "Feed post"
    assert items[0]["abstract"] == "Summary"


@pytest.mark.unit
def test_get_retries_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    def flaky(*args, **kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("boom")
        return FakeResponse(text="ok")

    monkeypatch.setattr(feed.httpx, "get", flaky)
    monkeypatch.setattr(feed.time, "sleep", lambda _seconds: None)

    response = feed._get("https://example.org")

    assert response.text == "ok"
    assert attempts["count"] == 3


@pytest.mark.integration
def test_refresh_uses_subscription_source(monkeypatch):
    feed.create_subscription("u1", kind="keyword", value="RAG", source="openalex")

    class Stub:
        name = "openalex"

        def fetch(self, subscription):
            return [{"external_id": "W1", "title": "From OpenAlex", "authors_json": None, "abstract": None, "url": None, "published_at": None}]

    monkeypatch.setitem(feed._SOURCES, "openalex", Stub())

    result = feed.refresh_feed("u1")

    assert result["items"] == 1
    assert result["errors"] == []
    assert feed.list_feed("u1")[0]["source"] == "openalex"


@pytest.mark.integration
def test_subscription_api_accepts_source():
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "alice"}
    client = TestClient(app)
    try:
        created = client.post(
            "/subscriptions",
            json={"kind": "keyword", "value": "RAG", "source": "rss"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["source"] == "rss"

        invalid = client.post(
            "/subscriptions",
            json={"kind": "keyword", "value": "RAG", "source": "scopus"},
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()
