"""MinerU Open API transport, result mapping and recovery behavior."""

import io
import json
import zipfile

import httpx
import pytest

from backend.rag.ingestion.mineru_api_backend import MinerUApiBackend, parse_result_zip
from backend.rag.ingestion.mineru_client import (
    MinerUBatchFile,
    MinerUClient,
    MinerUClientConfig,
    MinerUPermanentError,
)
from backend.rag.ingestion.normalizer import normalize_parser_output
from backend.rag.ingestion.parser_backend import RawParserResult
from backend.rag.ingestion.text_pdf_backend import TextPDFBackend


def _config(**overrides) -> MinerUClientConfig:
    data = {
        "base_url": "https://mineru.test",
        "token": "secret",
        "poll_interval": 0.0,
        "poll_max_interval": 0.0,
        "poll_timeout": 1.0,
        "max_retries": 2,
        "retry_base_delay": 0.0,
        "retry_max_delay": 0.0,
        "model_version": "pipeline",
        "language": "en",
    }
    data.update(overrides)
    return MinerUClientConfig(**data)


def _client(handler) -> MinerUClient:
    transport = httpx.MockTransport(handler)
    api_client = httpx.Client(
        base_url="https://mineru.test/api/v4",
        headers={"Authorization": "Bearer secret"},
        transport=transport,
    )
    plain_client = httpx.Client(transport=transport)
    return MinerUClient(
        _config(),
        api_client=api_client,
        plain_client=plain_client,
    )


def _result_zip() -> bytes:
    payload = [
        [
            {
                "type": "title",
                "content": {"title_content": [{"content": "Paper Title"}]},
                "bbox": [0, 0, 1000, 50],
            },
            {
                "type": "table",
                "content": {
                    "table_caption": [{"content": "Table 1"}],
                    "table_body": "<table><tr><td>42</td></tr></table>",
                    "table_footnote": [{"content": "source: synthetic"}],
                },
                "bbox": [0, 50, 1000, 300],
            },
        ]
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", "# Paper Title")
        archive.writestr(
            "layout.json",
            json.dumps({"pdf_info": [{"page_idx": 0, "page_size": [600, 800]}]}),
        )
        archive.writestr("abc_content_list_v2.json", json.dumps(payload))
    return buffer.getvalue()


@pytest.mark.unit
def test_submit_uses_data_id_and_configured_parameters():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            captured["body"] = json.loads(request.content)
            captured["auth"] = request.headers.get("Authorization")
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "batch_id": "batch-1",
                        "file_urls": ["https://upload.test/file-1"],
                    },
                    "msg": "ok",
                    "trace_id": "trace-1",
                },
            )
        if request.method == "PUT":
            captured["upload_auth"] = request.headers.get("Authorization")
            captured["upload_content_type"] = request.headers.get("Content-Type")
            captured["upload_body"] = request.content
            return httpx.Response(200)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = _client(handler)
    try:
        batch_id, urls = client.submit(
            [
                MinerUBatchFile(
                    filename="paper.pdf",
                    content=b"%PDF-1.7",
                    data_id="document-1",
                    page_ranges="1-20",
                )
            ]
        )
        client.upload(urls[0], b"%PDF-1.7")
    finally:
        client.close()

    assert batch_id == "batch-1"
    assert captured["auth"] == "Bearer secret"
    body = captured["body"]
    assert body["files"] == [
        {
            "name": "paper.pdf",
            "data_id": "document-1",
            "is_ocr": False,
            "page_ranges": "1-20",
        }
    ]
    assert body["model_version"] == "pipeline"
    assert body["language"] == "en"
    assert body["enable_formula"] is True
    assert body["enable_table"] is True
    assert captured["upload_auth"] is None
    assert captured["upload_content_type"] is None
    assert captured["upload_body"] == b"%PDF-1.7"


@pytest.mark.unit
def test_wait_handles_progress_and_intermediate_states():
    states = ["waiting-file", "pending", "running", "converting", "done"]
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        state = states.pop(0)
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "batch_id": "batch-1",
                    "extract_result": [
                        {
                            "state": state,
                            "data_id": "document-1",
                            "file_name": "paper.pdf",
                            "full_zip_url": "https://cdn.test/result.zip",
                            "extract_progress": {
                                "extracted_pages": 1,
                                "total_pages": 2,
                            },
                        }
                    ],
                },
                "msg": "ok",
                "trace_id": "trace-1",
            },
        )

    client = _client(handler)
    try:
        results = client.wait("batch-1")
    finally:
        client.close()

    assert calls == 5
    assert results[0]["state"] == "done"


@pytest.mark.unit
def test_wait_retries_429_then_succeeds():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "extract_result": [
                        {
                            "state": "done",
                            "data_id": "document-1",
                            "full_zip_url": "https://cdn.test/result.zip",
                        }
                    ]
                },
                "msg": "ok",
            },
        )

    client = _client(handler)
    try:
        client.wait("batch-1")
    finally:
        client.close()

    assert calls == 2


@pytest.mark.unit
def test_auth_error_is_not_retried():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401)

    client = _client(handler)
    try:
        with pytest.raises(MinerUPermanentError):
            client.wait("batch-1")
    finally:
        client.close()

    assert calls == 1


@pytest.mark.unit
def test_v2_table_body_and_footnote_are_kept():
    result = parse_result_zip(_result_zip())

    assert result.bbox_unit == "normalized_1000"
    table = result.pages[0]["blocks"][1]
    assert table["type"] == "table"
    assert "Table 1" in table["text"]
    assert "<table>" in table["text"]
    assert "source: synthetic" in table["text"]


@pytest.mark.unit
def test_v1_table_body_and_figure_caption_are_kept():
    payload = [
        {
            "type": "table",
            "table_caption": ["Table 2"],
            "table_body": "<table><tr><td>7</td></tr></table>",
            "table_footnote": ["note"],
            "bbox": [0, 0, 1000, 200],
            "page_idx": 0,
        },
        {
            "type": "image",
            "img_path": "images/figure.jpg",
            "image_caption": ["Figure 1"],
            "bbox": [0, 200, 1000, 400],
            "page_idx": 0,
        },
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", "# Paper")
        archive.writestr("abc_content_list.json", json.dumps(payload))

    result = parse_result_zip(buffer.getvalue())

    assert result.bbox_unit == "normalized_1000"
    table, figure = result.pages[0]["blocks"]
    assert table["type"] == "table"
    assert "Table 2" in table["text"]
    assert "<table>" in table["text"]
    assert "note" in table["text"]
    assert figure == {
        "type": "figure_caption",
        "text": "Figure 1",
        "bbox": [0, 200, 1000, 400],
    }


@pytest.mark.unit
def test_normalizer_canonicalizes_cloud_bbox_to_zero_one():
    raw = RawParserResult(
        markdown="",
        page_count=1,
        pages=[
            {
                "page_number": 1,
                "width": 600,
                "height": 800,
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": "hello",
                        "bbox": [100, 100, 500, 200],
                    }
                ],
            }
        ],
        bbox_unit="normalized_1000",
    )

    document_ir = normalize_parser_output(raw, "doc", "paper.pdf", TextPDFBackend())

    assert document_ir.bbox_unit == "normalized_1"
    assert document_ir.pages[0].width == 1.0
    block = document_ir.blocks[0]
    assert block.bbox.model_dump() == {
        "x0": 0.1,
        "y0": 0.1,
        "x1": 0.5,
        "y1": 0.2,
    }


@pytest.mark.unit
def test_resuming_an_existing_batch_does_not_submit_again():
    class FakeClient:
        def __init__(self) -> None:
            self.submitted = False

        def wait(self, batch_id, timeout=None):
            assert batch_id == "old-batch"
            return [
                {
                    "state": "done",
                    "data_id": "document-1",
                    "full_zip_url": "https://cdn.test/result.zip",
                }
            ]

        def submit(self, files):
            self.submitted = True
            raise AssertionError("resume must not submit a new batch")

        def upload(self, url, content):
            raise AssertionError("resume must not upload again")

        def download(self, url):
            return _result_zip()

    fake = FakeClient()
    backend = MinerUApiBackend(
        client=fake,
        document_id="document-1",
        resume_batch_id="old-batch",
    )

    result = backend.parse(b"%PDF-1.7", "paper.pdf")

    assert fake.submitted is False
    assert result.page_count == 1


@pytest.mark.unit
def test_submitting_a_batch_reports_the_batch_id_for_recovery():
    created: list[str] = []

    class FakeClient:
        def wait(self, batch_id, timeout=None):
            assert batch_id == "new-batch"
            return [
                {
                    "state": "done",
                    "data_id": "document-1",
                    "full_zip_url": "https://cdn.test/result.zip",
                }
            ]

        def submit(self, files):
            return "new-batch", ["https://upload.test/file-1"]

        def upload(self, url, content):
            assert url == "https://upload.test/file-1"

        def download(self, url):
            return _result_zip()

    backend = MinerUApiBackend(
        client=FakeClient(),
        document_id="document-1",
        on_batch_created=created.append,
    )

    backend.parse(b"%PDF-1.7", "paper.pdf")

    assert created == ["new-batch"]
