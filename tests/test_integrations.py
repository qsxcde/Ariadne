"""Token-based Zotero / Notion export with a fake HTTP client."""

import json

import pytest

from backend.application.integrations import export_to_notion, export_to_zotero
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeResponse()


def _seed() -> None:
    session = session_repo.create_session("Export", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="export.pdf",
        file_path="/tmp/export.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    paper_repo.update_paper_metadata(
        document["paper_id"],
        title="Attention Is All You Need",
        authors_json=json.dumps(["Ashish Vaswani", "Noam Shazeer"]),
        year=2017,
        venue="NeurIPS",
        doi="10.1000/test",
        url="https://example.com/paper",
    )


@pytest.mark.integration
def test_zotero_export_builds_items():
    _seed()
    client = FakeClient()

    result = export_to_zotero(
        "u1", api_key="secret", library_id="123", client=client
    )

    assert result == {"exported": 1}
    call = client.calls[0]
    assert call["url"] == "https://api.zotero.org/users/123/items"
    assert call["headers"]["Zotero-API-Key"] == "secret"
    assert call["json"][0]["title"] == "Attention Is All You Need"
    assert call["json"][0]["creators"][0]["lastName"] == "Vaswani"


@pytest.mark.integration
def test_notion_export_builds_pages():
    _seed()
    client = FakeClient()

    result = export_to_notion(
        "u1", token="secret", database_id="db-1", client=client
    )

    assert result == {"exported": 1}
    call = client.calls[0]
    assert call["url"] == "https://api.notion.com/v1/pages"
    assert call["headers"]["Authorization"] == "Bearer secret"
    assert call["json"]["parent"]["database_id"] == "db-1"
    assert call["json"]["properties"]["Name"]["title"][0]["text"]["content"] == "Attention Is All You Need"
