"""Optional real arXiv smoke test; enable with SCIPAL_NETWORK_TESTS=1."""

import os

import pytest

from backend.application.feed import ArxivFeedSource
from backend.application.paper_import import fetch_arxiv_reference

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


def test_arxiv_metadata_import_resolves_a_known_paper():
    reference = fetch_arxiv_reference("1706.03762")
    assert reference.arxiv_id == "1706.03762"
    assert reference.title == "Attention Is All You Need"
    assert reference.authors[0] == "Ashish Vaswani"
    assert reference.year == 2017
    assert "/pdf/1706.03762" in reference.pdf_url
