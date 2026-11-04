"""Reader block crops are scoped to the session and cached beside the IR."""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from backend.api.security import get_current_user
from backend.application.ingestion.documents import get_block_crop
from backend.main import app
from backend.domain.exceptions import BlockCropError, DocumentNotFoundError
from backend.storage.paths import session_document_file_path
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo


def _blank_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=100)
    with path.open("wb") as handle:
        writer.write(handle)


def _seed_document(
    tmp_path: Path, *, user_id: str | None = None
) -> tuple[str, str, Path]:
    session = session_repo.create_session("裁切测试", user_id=user_id)
    document_id = str(uuid.uuid4())
    pdf_path = session_document_file_path(session["id"], document_id)
    _blank_pdf(pdf_path)
    document = document_repo.create_document(
        session_id=session["id"],
        filename="paper.pdf",
        file_path=str(pdf_path),
        mime_type="application/pdf",
        file_size=pdf_path.stat().st_size,
        document_id=document_id,
    )

    ir_dir = pdf_path.parent / "parsed" / document["id"]
    ir_dir.mkdir(parents=True, exist_ok=True)
    ir_path = ir_dir / "document.ir.json"
    ir_path.write_text(
        json.dumps(
            {
                "document_id": document["id"],
                "filename": "paper.pdf",
                "page_count": 1,
                "parser_name": "mineru",
                "parser_version": "2.1",
                "bbox_unit": "normalized_1",
                "pages": [
                    {
                        "page_number": 1,
                        "width": 1.0,
                        "height": 1.0,
                        "rotation": 0,
                        "blocks": [
                            {
                                "id": "p1-ro0",
                                "page_number": 1,
                                "block_index": 0,
                                "type": "formula",
                                "text": "x = 1",
                                "bbox": {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.6},
                                "reading_order": 0,
                                "section_path": ["Method"],
                            }
                        ],
                    }
                ],
                "blocks": [],
                "outline": [],
                "quality_report": {
                    "parser_name": "mineru",
                    "parser_version": "2.1",
                    "page_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    document_repo.update_document_artifacts(
        document_id=document["id"],
        parsed_ir_path=str(ir_path),
        parsed_markdown_path=None,
        quality_report_path=None,
        parser_name="mineru",
        parser_version="2.1",
        parse_quality_status="good",
    )
    return session["id"], document["id"], ir_dir


@pytest.mark.integration
def test_block_crop_is_rendered_and_cached(tmp_path):
    session_id, document_id, ir_dir = _seed_document(tmp_path)

    image = get_block_crop(session_id, document_id, "p1-ro0", scale=2)

    assert image.startswith(b"\x89PNG")
    cache_path = ir_dir / "crops" / "p1-ro0-2x.png"
    assert cache_path.is_file()
    assert cache_path.read_bytes() == image


@pytest.mark.integration
def test_block_crop_requires_known_block(tmp_path):
    session_id, document_id, _ = _seed_document(tmp_path)

    with pytest.raises(BlockCropError):
        get_block_crop(session_id, document_id, "p1-ro99")

    with pytest.raises(BlockCropError):
        get_block_crop(session_id, document_id, "../escape")


@pytest.mark.integration
def test_block_crop_endpoint_returns_png(tmp_path):
    session_id, document_id, _ = _seed_document(tmp_path, user_id="u1")
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "tester"}
    try:
        # No lifespan: startup recovery would delete the seeded uploaded document.
        client = TestClient(app)
        response = client.get(
            f"/sessions/{session_id}/documents/{document_id}/blocks/p1-ro0/crop?scale=2"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


@pytest.mark.integration
def test_block_crop_is_scoped_to_session(tmp_path):
    _, document_id, _ = _seed_document(tmp_path)
    other_session = session_repo.create_session("另一个会话")

    with pytest.raises(DocumentNotFoundError):
        get_block_crop(other_session["id"], document_id, "p1-ro0")
