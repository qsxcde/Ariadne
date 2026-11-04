"""Optional real OpenAlex citation smoke test."""

import os

import pytest

from backend.application.library.citations import get_citation_graph
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo

pytestmark = [
    pytest.mark.network,
    pytest.mark.skipif(
        os.getenv("SCIPAL_NETWORK_TESTS") != "1",
        reason="set SCIPAL_NETWORK_TESTS=1 to call OpenAlex",
    ),
]


def test_openalex_returns_citations():
    session = session_repo.create_session("OpenAlex", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="attention.pdf",
        file_path="/tmp/attention.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    paper_repo.update_paper_metadata(
        document["paper_id"],
        title="Attention Is All You Need",
        doi="10.48550/arXiv.1706.03762",
    )

    result = get_citation_graph(document["paper_id"], "u1")

    assert result["openalex_id"].startswith("https://openalex.org/")
    assert result["cited_by_count"] > 0
    assert result["references"]
