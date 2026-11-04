"""Optional real feed-source smoke tests; enable with SCIPAL_NETWORK_TESTS=1."""

import os

import pytest

from backend.application.follow import feed

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.getenv("SCIPAL_NETWORK_TESTS") != "1",
        reason="set SCIPAL_NETWORK_TESTS=1 to call real feed APIs",
    ),
]


def _sub(value: str, source: str):
    return {"value": value, "kind": "keyword", "source": source}


def test_openalex_source_returns_items():
    items = feed.OpenAlexFeedSource().fetch(_sub("retrieval augmented generation", "openalex"))
    assert items
    assert items[0]["title"]
    assert items[0]["external_id"].startswith("https://openalex.org/")


def test_pubmed_source_returns_items():
    items = feed.PubMedFeedSource().fetch(_sub("cancer immunotherapy", "pubmed"))
    assert items
    assert items[0]["external_id"].startswith("pubmed:")


def test_rss_source_returns_items():
    items = feed.RssFeedSource().fetch(_sub("https://rss.arxiv.org/rss/cs.CL", "rss"))
    assert items
    assert items[0]["title"]
