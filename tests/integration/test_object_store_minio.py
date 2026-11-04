import os
import uuid

import pytest

from backend.storage.object_store import S3ObjectStore

TEST_S3_ENDPOINT = os.getenv("TEST_S3_ENDPOINT")
TEST_S3_BUCKET = os.getenv("TEST_S3_BUCKET", "ariadne")
TEST_S3_ACCESS_KEY = os.getenv("TEST_S3_ACCESS_KEY", "ariadne")
TEST_S3_SECRET_KEY = os.getenv("TEST_S3_SECRET_KEY", "ariadne_dev_secret")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_S3_ENDPOINT,
        reason="TEST_S3_ENDPOINT is not configured",
    ),
]


def _configure_s3(monkeypatch, tmp_path):
    from backend import config
    from backend.storage.object_store import reset_object_store

    monkeypatch.setattr(config.settings, "object_store_backend", "s3")
    monkeypatch.setattr(config.settings, "object_store_endpoint", TEST_S3_ENDPOINT)
    monkeypatch.setattr(config.settings, "object_store_bucket", TEST_S3_BUCKET)
    monkeypatch.setattr(config.settings, "object_store_access_key", TEST_S3_ACCESS_KEY)
    monkeypatch.setattr(config.settings, "object_store_secret_key", TEST_S3_SECRET_KEY)
    monkeypatch.setattr(config.settings, "object_store_region", "us-east-1")
    monkeypatch.setattr(config.settings, "object_store_use_ssl", False)
    monkeypatch.setattr(
        config.settings, "object_store_cache_dir", str(tmp_path / "object-cache")
    )
    reset_object_store()


def test_minio_round_trip_and_prefix_delete(tmp_path):
    store = S3ObjectStore(
        bucket=TEST_S3_BUCKET,
        endpoint=TEST_S3_ENDPOINT,
        access_key=TEST_S3_ACCESS_KEY,
        secret_key=TEST_S3_SECRET_KEY,
        region="us-east-1",
        use_ssl=False,
        cache_dir=tmp_path / "cache",
    )
    prefix = f"tests/{uuid.uuid4()}"
    try:
        ref = store.put_bytes(f"{prefix}/a.txt", b"hello minio")
        assert ref == f"{prefix}/a.txt"
        assert store.exists(ref)
        assert store.get_bytes(ref) == b"hello minio"
        assert store.materialize(ref).read_bytes() == b"hello minio"

        store.put_bytes(f"{prefix}/nested/b.txt", b"nested")
        assert store.exists(f"{prefix}/nested/b.txt")
        store.delete_prefix(prefix)
        assert not store.exists(ref)
        assert not store.exists(f"{prefix}/nested/b.txt")
    finally:
        store.delete_prefix(prefix)


def test_upload_intake_stores_pdf_in_minio(tmp_path, monkeypatch):
    from backend.application.ingestion.documents import (
        get_document_file,
        intake_document_upload,
    )
    from backend.storage.object_store import get_object_store
    from backend.storage.paths import remove_session_dir
    from backend.storage.sqlite import sessions

    _configure_s3(monkeypatch, tmp_path)
    session = sessions.create_session("s3 upload")
    pdf_bytes = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n"
    intake = intake_document_upload(
        session_id=session["id"],
        filename="paper.pdf",
        mime_type="application/pdf",
        pdf_bytes=pdf_bytes,
        file_size=len(pdf_bytes),
    )

    document = intake["document"]
    assert document["file_path"].startswith(f"raw/{session['id']}/")
    store = get_object_store()
    assert store.exists(document["file_path"])
    assert get_document_file(session["id"], document["id"]).read_bytes() == pdf_bytes

    remove_session_dir(session["id"])
    assert not store.exists(document["file_path"])


def test_index_snapshot_round_trip_via_minio(tmp_path, monkeypatch):
    pytest.importorskip("faiss", reason="faiss-cpu is not installed")
    pytest.importorskip("torch", reason="torch is not installed")

    from backend.adapters.vector import faiss_store as vector_store
    from backend.adapters.vector.store_cache import discard_store, get_store_for_snapshot
    from backend.application.ingestion import indexing
    from backend.domain.models import Chunk, ChunkMetadata
    from backend.storage.object_store import get_object_store
    from backend.storage.sqlite import chunks as chunk_repo
    from backend.storage.sqlite import documents as document_repo
    from backend.storage.sqlite import sessions

    _configure_s3(monkeypatch, tmp_path)
    monkeypatch.setattr(vector_store, "_default_embed", _embed)

    session = sessions.create_session("s3 snapshot")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="paper.pdf",
        file_path=f"raw/{session['id']}/paper.pdf",
        mime_type="application/pdf",
        file_size=1024,
    )
    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text=text,
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Introduction",
                    chunk_index=position,
                    type="paragraph",
                ),
            )
            for position, text in enumerate(["alpha", "beta"])
        ],
    )

    snapshot = indexing.build_candidate_snapshot(session["id"], document["id"])
    assert snapshot["index_path"].startswith("index/")
    store = get_object_store()
    assert store.exists(snapshot["index_path"])
    assert store.exists(snapshot["chunks_path"])

    loaded = get_store_for_snapshot(snapshot)
    assert loaded.list_chunks()

    discard_store(session["id"])
    indexing.cleanup_snapshot_files(snapshot)
    assert not store.exists(snapshot["index_path"])
    assert not store.exists(snapshot["chunks_path"])


def test_file_migration_uploads_artifacts_and_rewrites_refs(tmp_path, monkeypatch):
    from backend import config
    from backend.scripts import migrate_files_to_object_store as migrate_files
    from backend.storage.object_store import get_object_store
    from backend.storage.sqlite import documents as document_repo
    from backend.storage.sqlite import index_snapshots as snapshot_repo
    from backend.storage.sqlite import indexes as index_repo
    from backend.storage.sqlite import sessions

    _configure_s3(monkeypatch, tmp_path)
    data_root = config.data_dir()
    session = sessions.create_session("migration")
    document_id = str(uuid.uuid4())
    pdf_path = data_root / "raw" / session["id"] / f"{document_id}.pdf"
    _write(pdf_path, b"%PDF-1.7")
    artifact_dir = data_root / "raw" / session["id"] / "parsed" / document_id
    ir_path = _write(artifact_dir / "document.ir.json", b"{}")
    _write(artifact_dir / "document.md", b"# paper")
    _write(artifact_dir / "document.normalized.md", b"# paper")
    _write(artifact_dir / "quality_report.json", b"{}")
    _write(artifact_dir / "crops" / "b1-2x.png", b"png")
    document_repo.create_document(
        session_id=session["id"],
        filename="paper.pdf",
        file_path=str(pdf_path),
        mime_type="application/pdf",
        file_size=8,
        document_id=document_id,
    )
    document_repo.update_document_artifacts(
        document_id=document_id,
        parsed_ir_path=str(ir_path),
        parsed_markdown_path=str(artifact_dir / "document.md"),
        quality_report_path=str(artifact_dir / "quality_report.json"),
        parser_name="mineru",
        parser_version="2.1",
        parse_quality_status="good",
    )
    snapshot_index = _write(
        data_root / "index" / session["id"] / "legacy.faiss.index", b"index"
    )
    snapshot_chunks = _write(
        data_root / "index" / session["id"] / "legacy.chunks.json", b"[]"
    )
    snapshot = snapshot_repo.create_building_snapshot(
        session_id=session["id"],
        index_path=str(snapshot_index),
        chunks_path=str(snapshot_chunks),
        document_ids=[document_id],
    )
    _write(data_root / "index" / session["id"] / "legacy2.faiss.index", b"legacy")
    _write(data_root / "index" / session["id"] / "legacy2.chunks.json", b"[]")
    index_repo.upsert_index(
        session["id"],
        str(data_root / "index" / session["id"] / "legacy2.faiss.index"),
        str(data_root / "index" / session["id"] / "legacy2.chunks.json"),
        "ready",
    )

    dry_run = migrate_files.run(apply=False)
    assert dry_run["uploads"] >= 9
    assert document_repo.get_document(document_id)["file_path"] == str(pdf_path)

    report = migrate_files.run(apply=True)
    assert report["uploads"] == dry_run["uploads"]
    store = get_object_store()
    migrated = document_repo.get_document(document_id)
    assert migrated["file_path"] == f"raw/{session['id']}/{document_id}.pdf"
    assert migrated["parsed_ir_path"] == (
        f"raw/{session['id']}/parsed/{document_id}/document.ir.json"
    )
    assert store.exists(migrated["file_path"])
    assert store.exists(migrated["parsed_ir_path"])
    assert store.exists(
        f"raw/{session['id']}/parsed/{document_id}/document.normalized.md"
    )
    assert store.exists(f"raw/{session['id']}/parsed/{document_id}/crops/b1-2x.png")
    assert snapshot_repo.get_snapshot(snapshot["id"])["index_path"].startswith("index/")
    assert index_repo.get_index(session["id"])["index_path"].startswith("index/")

    second = migrate_files.run(apply=True)
    assert second["uploads"] == 0
    assert second["updates"] == 0


def _write(path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        seed = sum(ord(char) for char in text) or 1
        vectors.append([float((seed * (position + 1)) % 17) for position in range(8)])
    return vectors

