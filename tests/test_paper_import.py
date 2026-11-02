"""arXiv / DOI / URL import (M1.2.1)."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application import paper_import
from backend.domain.exceptions import (
    DuplicatePaperError,
    ImportFetchError,
    ImportResolutionError,
)
from backend.main import app

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"

ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.00001v2</id>
    <published>2024-01-02T00:00:00Z</published>
    <title>Attention   Is All You Need</title>
    <summary> We propose the Transformer. </summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:doi>10.1000/xyz</arxiv:doi>
    <arxiv:journal_ref>NeurIPS 2017</arxiv:journal_ref>
    <link href="http://arxiv.org/abs/2401.00001v2" rel="alternate" type="text/html"/>
    <link title="pdf" href="http://arxiv.org/pdf/2401.00001v2" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""

CROSSREF = {
    "title": ["Retrieval-Augmented Generation for Knowledge-Intensive NLP"],
    "author": [
        {"given": "Patrick", "family": "Lewis"},
        {"given": "Ethan", "family": "Perez"},
    ],
    "issued": {"date-parts": [[2020, 5, 22]]},
    "container-title": ["NeurIPS"],
    "abstract": "<jats:p>We explore RAG.</jats:p>",
    "URL": "https://doi.org/10.5555/abc",
}

LANDING_HTML = """<html><head>
<title>Fallback title</title>
<meta name="citation_title" content="A Landing Page Paper">
<meta name="citation_author" content="Ada Lovelace">
<meta name="citation_author" content="Alan Turing">
<meta name="citation_publication_date" content="2021/03/04">
<meta name="citation_journal_title" content="Journal of Tests">
<meta name="citation_doi" content="10.1234/landing">
<meta name="citation_pdf_url" content="/files/paper.pdf">
<meta name="citation_abstract" content="A paper imported from a landing page.">
</head><body></body></html>"""


def _handler(url: str, *, params=None, timeout: float = 20) -> httpx.Response:
    if "export.arxiv.org" in url:
        return httpx.Response(
            200, text=ARXIV_XML, headers={"content-type": "application/atom+xml"}
        )
    if "api.crossref.org" in url:
        return httpx.Response(200, json={"message": CROSSREF})
    if ".pdf" in url or "/pdf/" in url:
        return httpx.Response(
            200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
        )
    return httpx.Response(200, text=LANDING_HTML, headers={"content-type": "text/html"})


@pytest.fixture
def fake_http(monkeypatch):
    monkeypatch.setattr(paper_import, "_http_get", _handler)
    return _handler


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "u1",
        "username": "alice",
    }
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2401.00001", "2401.00001"),
        ("arXiv:2401.00001v3", "2401.00001"),
        ("https://arxiv.org/abs/2401.00001v2", "2401.00001"),
        ("https://arxiv.org/pdf/2401.00001.pdf", "2401.00001"),
        ("hep-th/9901001v1", "hep-th/9901001"),
    ],
)
def test_normalize_arxiv_id(raw: str, expected: str):
    assert paper_import.normalize_arxiv_id(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["", "not-an-id", "https://example.org/paper"])
def test_normalize_arxiv_id_rejects_garbage(raw: str):
    with pytest.raises(ImportResolutionError):
        paper_import.normalize_arxiv_id(raw)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.1000/xyz", "10.1000/xyz"),
        ("doi:10.1000/xyz", "10.1000/xyz"),
        ("https://doi.org/10.1000/xyz", "10.1000/xyz"),
        ("http://dx.doi.org/10.1000/xyz", "10.1000/xyz"),
    ],
)
def test_normalize_doi(raw: str, expected: str):
    assert paper_import.normalize_doi(raw) == expected


@pytest.mark.unit
def test_normalize_url_requires_scheme():
    assert paper_import.normalize_url(" https://example.org/a ") == "https://example.org/a"
    with pytest.raises(ImportResolutionError):
        paper_import.normalize_url("example.org/a")


@pytest.mark.unit
def test_unknown_source_is_rejected():
    with pytest.raises(ImportResolutionError):
        paper_import.resolve_reference("pubmed", "123")


@pytest.mark.integration
def test_arxiv_import_creates_paper_session_document_and_job(fake_http):
    result = paper_import.import_paper_reference(
        user_id="u1",
        source="arxiv",
        identifier="https://arxiv.org/abs/2401.00001v2",
    )

    paper = result["paper"]
    assert paper["title"] == "Attention Is All You Need"
    assert json.loads(paper["authors_json"]) == ["Ashish Vaswani", "Noam Shazeer"]
    assert paper["year"] == 2024
    assert paper["venue"] == "NeurIPS 2017"
    assert paper["doi"] == "10.1000/xyz"
    assert paper["arxiv_id"] == "2401.00001"
    assert paper["abstract"] == "We propose the Transformer."
    assert paper["url"] == "https://arxiv.org/abs/2401.00001"

    assert result["pdf_imported"] is True
    assert result["warning"] is None
    assert result["session"]["paper_id"] == paper["id"]
    assert result["document"]["status"] == "uploaded"
    assert result["job"]["status"] == "queued"


@pytest.mark.integration
def test_arxiv_import_is_deduplicated(fake_http):
    first = paper_import.import_paper_reference(
        user_id="u1", source="arxiv", identifier="2401.00001"
    )
    with pytest.raises(DuplicatePaperError) as excinfo:
        paper_import.import_paper_reference(
            user_id="u1", source="arxiv", identifier="arXiv:2401.00001v2"
        )
    assert excinfo.value.paper_id == first["paper"]["id"]


@pytest.mark.integration
def test_doi_import_without_pdf_keeps_metadata_only(fake_http):
    result = paper_import.import_paper_reference(
        user_id="u1", source="doi", identifier="https://doi.org/10.5555/abc"
    )

    paper = result["paper"]
    assert paper["title"] == "Retrieval-Augmented Generation for Knowledge-Intensive NLP"
    assert json.loads(paper["authors_json"]) == ["Patrick Lewis", "Ethan Perez"]
    assert paper["year"] == 2020
    assert paper["venue"] == "NeurIPS"
    assert paper["doi"] == "10.5555/abc"
    assert paper["abstract"] == "We explore RAG."
    assert paper["reading_status"] == "inbox"

    assert result["pdf_imported"] is False
    assert result["session"] is None
    assert result["document"] is None
    assert result["job"] is None
    assert result["warning"] == "来源未提供可下载的 PDF，仅导入元数据"


@pytest.mark.integration
def test_url_import_reads_citation_meta_tags(fake_http):
    result = paper_import.import_paper_reference(
        user_id="u1", source="url", identifier="https://example.org/paper"
    )

    paper = result["paper"]
    assert paper["title"] == "A Landing Page Paper"
    assert json.loads(paper["authors_json"]) == ["Ada Lovelace", "Alan Turing"]
    assert paper["year"] == 2021
    assert paper["venue"] == "Journal of Tests"
    assert paper["doi"] == "10.1234/landing"
    assert paper["abstract"] == "A paper imported from a landing page."
    assert paper["arxiv_id"] is None
    assert result["pdf_imported"] is True
    assert result["document"]["status"] == "uploaded"


@pytest.mark.integration
def test_pdf_download_failure_falls_back_to_metadata(monkeypatch):
    def failing(url: str, *, params=None, timeout: float = 20) -> httpx.Response:
        if "export.arxiv.org" in url:
            return httpx.Response(200, text=ARXIV_XML)
        raise ImportFetchError("PDF 服务不可用")

    monkeypatch.setattr(paper_import, "_http_get", failing)
    result = paper_import.import_paper_reference(
        user_id="u1", source="arxiv", identifier="2401.00001"
    )

    assert result["pdf_imported"] is False
    assert result["document"] is None
    assert result["warning"] and "PDF 下载失败" in result["warning"]
    assert result["paper"]["arxiv_id"] == "2401.00001"


@pytest.mark.integration
def test_import_endpoint_returns_202_and_maps_errors(client: TestClient, fake_http):
    response = client.post(
        "/papers/import",
        json={"source": "arxiv", "identifier": "2401.00001"},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["paper"]["title"] == "Attention Is All You Need"
    assert body["pdf_imported"] is True
    assert body["document_status"] == "uploaded"
    assert body["job_status"] == "queued"

    duplicate = client.post(
        "/papers/import",
        json={"source": "arxiv", "identifier": "2401.00001"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["paper_id"] == body["paper"]["id"]

    invalid = client.post(
        "/papers/import",
        json={"source": "arxiv", "identifier": "nonsense"},
    )
    assert invalid.status_code == 422

    listing = client.get("/papers")
    assert [row["id"] for row in listing.json()] == [body["paper"]["id"]]
