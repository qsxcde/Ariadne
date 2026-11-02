"""OpenAlex citation graph with a fake HTTP client."""

import pytest

from backend.application.citations import get_citation_graph
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeClient:
    def get(self, url: str, **kwargs):
        if "filter" in (kwargs.get("params") or {}):
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": "https://openalex.org/W2",
                            "title": "Referenced Paper",
                            "doi": "https://doi.org/10.1/ref",
                            "publication_year": 2019,
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "id": "https://openalex.org/W1",
                "cited_by_count": 42,
                "referenced_works": ["https://openalex.org/W2"],
            }
        )


def _seed() -> str:
    session = session_repo.create_session("Citations", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="citations.pdf",
        file_path="/tmp/citations.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    paper_repo.update_paper_metadata(document["paper_id"], doi="10.1000/test")
    return document["paper_id"]


@pytest.mark.integration
def test_citation_graph_reads_openalex_payload():
    paper_id = _seed()

    result = get_citation_graph(paper_id, "u1", client=FakeClient())

    assert result["openalex_id"] == "https://openalex.org/W1"
    assert result["cited_by_count"] == 42
    assert result["reference_count"] == 1
    assert result["references"][0]["title"] == "Referenced Paper"


@pytest.mark.unit
def test_citation_graph_requires_doi_or_arxiv():
    session = session_repo.create_session("No ids", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="no-ids.pdf",
        file_path="/tmp/no-ids.pdf",
        mime_type="application/pdf",
        file_size=10,
    )

    with pytest.raises(ValueError, match="DOI or arXiv"):
        get_citation_graph(document["paper_id"], "u1", client=FakeClient())
