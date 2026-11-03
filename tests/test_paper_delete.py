"""论文删除：级联清理会话、文档、批注、集合关联、阅读日志与磁盘产物。"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application import papers as paper_service
from backend.domain.exceptions import JobInProgressError, PaperNotFoundError
from backend.domain.models import Chunk, ChunkMetadata
from backend.domain.states import DocumentStage
from backend.main import app
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import jobs as job_repo
from backend.storage.sqlite import messages as message_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import reading as reading_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.connection import connect

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"


def _seed_paper_with_artifacts(tmp_path: Path, *, user_id: str | None = "u1") -> dict:
    session = session_repo.create_session("删除测试", user_id=user_id)
    pdf_path = tmp_path / "data" / "raw" / session["id"] / "doc.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(PDF_BYTES)

    document = document_repo.create_document(
        session_id=session["id"],
        filename="doc.pdf",
        file_path=str(pdf_path),
        mime_type="application/pdf",
        file_size=len(PDF_BYTES),
    )
    paper_id = document["paper_id"]

    artifact_dir = tmp_path / "data" / "parsed" / session["id"] / document["id"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    ir_path = artifact_dir / "document.ir.json"
    ir_path.write_text("{}", encoding="utf-8")
    document_repo.update_document_artifacts(
        document_id=document["id"],
        parsed_ir_path=str(ir_path),
        parsed_markdown_path=str(artifact_dir / "document.md"),
        quality_report_path=None,
        parser_name="mineru",
        parser_version="2.1",
        parse_quality_status="good",
    )

    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text="内容",
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="1",
                    chunk_index=0,
                    type="paragraph",
                ),
            )
        ],
    )
    message_repo.create_message(session["id"], "user", "这篇讲了什么？")
    annotation_repo.create_annotation(
        paper_id=paper_id,
        annotation_type="note",
        content="重点",
    )
    collection = collection_repo.create_collection(user_id=user_id, name="集合")
    collection_repo.add_paper_to_collection(collection["id"], paper_id)
    collection_repo.add_tag(paper_id, "nlp")
    reading_repo.record_reading(user_id, paper_id, 60, day="2026-11-03")

    return {
        "session_id": session["id"],
        "document_id": document["id"],
        "paper_id": paper_id,
        "collection_id": collection["id"],
        "artifact_dir": artifact_dir,
        "pdf_path": pdf_path,
    }


@pytest.mark.integration
def test_delete_paper_removes_related_rows_and_disk_artifacts(tmp_path: Path):
    seed = _seed_paper_with_artifacts(tmp_path)
    paper_id = seed["paper_id"]

    paper_service.delete_paper(paper_id, "u1")

    assert paper_repo.get_paper(paper_id) is None
    assert session_repo.get_session(seed["session_id"]) is None
    assert document_repo.get_document(seed["document_id"]) is None
    assert chunk_repo.list_chunks(seed["session_id"]) == []
    assert message_repo.list_messages(seed["session_id"]) == []
    assert annotation_repo.list_annotations(paper_id) == []
    assert collection_repo.list_tags(paper_id) == []
    assert (
        collection_repo.list_collections_for_paper(paper_id) == []
    )
    assert not seed["pdf_path"].exists()
    assert not seed["artifact_dir"].exists()

    with connect() as conn:
        reading_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM reading_log WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        assert reading_rows is not None and reading_rows["n"] == 0
        session_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM sessions WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        assert session_rows is not None and session_rows["n"] == 0


@pytest.mark.integration
def test_delete_paper_rejects_foreign_paper(tmp_path: Path):
    seed = _seed_paper_with_artifacts(tmp_path, user_id="u1")

    with pytest.raises(PaperNotFoundError):
        paper_service.delete_paper(seed["paper_id"], "u2")

    assert paper_repo.get_paper(seed["paper_id"]) is not None


@pytest.mark.integration
def test_delete_paper_is_rejected_while_ingesting(tmp_path: Path):
    seed = _seed_paper_with_artifacts(tmp_path)
    job = job_repo.create_job(
        session_id=seed["session_id"],
        document_id=seed["document_id"],
        job_type="document_ingestion",
        stage=DocumentStage.uploaded,
    )
    assert job_repo.mark_job_running(job["id"]) is True

    with pytest.raises(JobInProgressError):
        paper_service.delete_paper(seed["paper_id"], "u1")

    assert paper_repo.get_paper(seed["paper_id"]) is not None
    assert document_repo.get_document(seed["document_id"]) is not None


@pytest.mark.integration
def test_delete_paper_twice_returns_not_found(tmp_path: Path):
    seed = _seed_paper_with_artifacts(tmp_path)
    paper_service.delete_paper(seed["paper_id"], "u1")

    with pytest.raises(PaperNotFoundError):
        paper_service.delete_paper(seed["paper_id"], "u1")


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


@pytest.mark.integration
def test_delete_paper_endpoint(client: TestClient):
    upload = client.post(
        "/papers",
        files={"file": ("attention.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 202, upload.text
    paper_id = upload.json()["paper"]["id"]

    deleted = client.delete(f"/papers/{paper_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"status": "deleted"}

    assert client.get(f"/papers/{paper_id}").status_code == 404
    assert [row["id"] for row in client.get("/papers").json()] == []


@pytest.mark.integration
def test_delete_paper_endpoint_missing_returns_404(client: TestClient):
    response = client.delete("/papers/paper_missing")
    assert response.status_code == 404
