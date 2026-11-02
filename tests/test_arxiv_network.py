"""Optional real arXiv smoke test; enable with SCIPAL_NETWORK_TESTS=1."""

import os

import pytest

from backend.application.feed import ArxivFeedSource

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.getenv("SCIPAL_NETWORK_TESTS") != "1",
        reason="set SCIPAL_NETWORK_TESTS=1 to call the real arXiv API",
    ),
]


def test_arxiv_source_returns_items():
    items = ArxivFeedSource().fetch({"value": "RAG", "kind": "keyword"})
    assert items
    assert items[0]["external_id"].startswith("http")
    assert items[0]["title"]
