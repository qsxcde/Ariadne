"""Full index snapshot pipeline: build, promote, load and roll back.

The snapshot model is the most load-bearing design in Ariadne: FAISS cannot
delete vectors in place, so every change rebuilds a candidate index and either
promotes it atomically or rolls back. These tests exercise the real FAISS files
with a deterministic 8-dimensional embedder, so they stay fast and offline.
"""

from pathlib import Path
from types import SimpleNamespace

import asyncio
import pytest

# These tests exercise real FAISS files. CI installs only the light dependency
# set, so skip there instead of failing collection; a full-dependency CI job is
# tracked in the remediation plan (P7.4).
pytest.importorskip("faiss", reason="faiss-cpu is not installed")
pytest.importorskip("torch", reason="torch is not installed")

from backend.application.ingestion import indexing
from backend.domain.exceptions import SnapshotCommitError
from backend.domain.models import Chunk, ChunkMetadata
from backend.adapters.vector import faiss_store as vector_store
from backend.adapters.vector.faiss_store import FAISSVectorStore
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import index_snapshots as snapshot_repo
from backend.storage.sqlite import indexes as index_repo
from backend.storage.sqlite import sessions

DIM = 8


def _embed(texts: list[str]) -> list[list[float]]:
    """Deterministic stand-in for the real embedding model."""
    vectors = []
    for text in texts:
        seed = sum(ord(char) for char in text) or 1
        vectors.append([float((seed * (position + 1)) % 17) for position in range(DIM)])
    return vectors


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    monkeypatch.setattr(vector_store, "_default_embed", _embed)


def _chunk(paper_id: str, index: int, text: str) -> Chunk:
    return Chunk(
        text=text,
        metadata=ChunkMetadata(
            paper_id=paper_id,
            section="Introduction",
            chunk_index=index,
            type="paragraph",
        ),
    )


def _seed(session_id: str, texts: list[str]) -> dict:
    """Create a document plus its chunks; chunk.paper_id is the document id (FK)."""
    document = document_repo.create_document(
        session_id=session_id,
        filename="paper.pdf",
        file_path="/tmp/paper.pdf",
        mime_type="application/pdf",
        file_size=1024,
    )
    chunk_repo.insert_chunks(
        session_id,
        document["id"],
        [
            _chunk(document["id"], position, text)
            for position, text in enumerate(texts)
        ],
    )
    return document


@pytest.mark.integration
def test_snapshot_records_embedding_and_skips_incompatible_previous(monkeypatch):
    session_id = sessions.create_session("embedding fingerprint")["id"]
    first_document = _seed(session_id, ["alpha", "beta"])
    runtime_a = SimpleNamespace(
        fingerprint="remote|siliconflow|model-a|8",
        model="model-a",
        dim=DIM,
        cache_key="a",
        embed=_embed,
    )
    candidate = indexing.build_candidate_snapshot(
        session_id, first_document["id"], embedding=runtime_a
    )
    assert candidate["embedding_fingerprint"] == "remote|siliconflow|model-a|8"
    assert candidate["embedding_model"] == "model-a"
    indexing.commit_ready_snapshot(
        session_id, candidate["id"], first_document["id"], chunk_count=2
    )

    second_document = _seed(session_id, ["gamma"])
    runtime_b = SimpleNamespace(
        fingerprint="remote|siliconflow|model-b|8",
        model="model-b",
        dim=DIM,
        cache_key="b",
        embed=_embed,
    )

    def fail_load(cls, *args, **kwargs):
        raise AssertionError("an incompatible snapshot must not be reused")

    with monkeypatch.context() as patcher:
        patcher.setattr(FAISSVectorStore, "load", classmethod(fail_load))
        rebuilt = indexing.build_candidate_snapshot(
            session_id, second_document["id"], embedding=runtime_b
        )

    assert rebuilt["embedding_fingerprint"] == "remote|siliconflow|model-b|8"
    assert rebuilt["embedding_model"] == "model-b"
    store = FAISSVectorStore.load(
        index_path=Path(rebuilt["index_path"]),
        chunks_path=Path(rebuilt["chunks_path"]),
    )
    assert len(store.list_chunks()) == 3


@pytest.mark.integration
def test_embedding_matches_treats_legacy_snapshots_as_env(monkeypatch):
    from backend.application.ingestion import indexing

    runtime = SimpleNamespace(fingerprint="remote|siliconflow|model-a|8")
    monkeypatch.setattr(indexing, "env_embedding_fingerprint", lambda: runtime.fingerprint)

    assert indexing._embedding_matches(
        {"embedding_fingerprint": None}, runtime
    )
    assert not indexing._embedding_matches(
        {"embedding_fingerprint": "remote|siliconflow|model-b|8"}, runtime
    )


@pytest.mark.integration
def test_resolve_store_rejects_stale_embedding_and_rebuild_recovers():
    from backend.application.conversation import sessions as session_service
    from backend.application.conversation.session_index import resolve_session_store
    from backend.domain.exceptions import IndexEmbeddingMismatchError

    session_id = sessions.create_session("stale embedding")["id"]
    document = _seed(session_id, ["alpha", "beta"])
    runtime_a = SimpleNamespace(
        fingerprint="remote|siliconflow|model-a|8",
        model="model-a",
        dim=DIM,
        cache_key="a",
        embed=_embed,
    )
    candidate = indexing.build_candidate_snapshot(
        session_id, document["id"], embedding=runtime_a
    )
    indexing.commit_ready_snapshot(
        session_id, candidate["id"], document["id"], chunk_count=2
    )

    runtime_b = SimpleNamespace(
        fingerprint="remote|siliconflow|model-b|8",
        model="model-b",
        dim=DIM,
        cache_key="b",
        embed=_embed,
    )
    with pytest.raises(IndexEmbeddingMismatchError):
        asyncio.run(resolve_session_store(session_id, embedding=runtime_b))

    result = session_service.rebuild_index(session_id, None, embedding=runtime_b)
    assert result["status"] == "ready"
    rebuilt = snapshot_repo.get_active_ready_snapshot(session_id)
    assert rebuilt is not None
    assert rebuilt["embedding_fingerprint"] == runtime_b.fingerprint

    store, _ = asyncio.run(resolve_session_store(session_id, embedding=runtime_b))
    assert len(store.list_chunks()) == 2


@pytest.mark.integration
def test_build_promote_and_load_round_trip():
    session_id = sessions.create_session("pipeline")["id"]
    document = _seed(session_id, ["alpha", "beta", "gamma"])

    candidate = indexing.build_candidate_snapshot(session_id, document["id"])
    assert candidate["status"] == "building"
    assert Path(candidate["index_path"]).exists()
    assert Path(candidate["chunks_path"]).exists()
    assert snapshot_repo.get_active_ready_snapshot(session_id) is None

    ready = indexing.commit_ready_snapshot(
        session_id, candidate["id"], document["id"], chunk_count=3
    )

    assert ready["status"] == "ready"
    assert snapshot_repo.get_active_ready_snapshot(session_id)["id"] == candidate["id"]
    assert document_repo.get_document(document["id"])["status"] == "ready"
    assert index_repo.get_index(session_id)["status"] == "ready"

    store = FAISSVectorStore.load(
        index_path=Path(ready["index_path"]),
        chunks_path=Path(ready["chunks_path"]),
    )
    assert len(store.list_chunks()) == 3


@pytest.mark.integration
def test_second_build_indexes_only_new_chunks():
    session_id = sessions.create_session("incremental")["id"]
    first_document = _seed(session_id, ["alpha", "beta", "gamma"])
    first = indexing.build_candidate_snapshot(session_id, first_document["id"])
    indexing.commit_ready_snapshot(session_id, first["id"], first_document["id"], 3)

    second_document = _seed(session_id, ["delta"])
    second = indexing.build_candidate_snapshot(session_id, second_document["id"])

    store = FAISSVectorStore.load(
        index_path=Path(second["index_path"]),
        chunks_path=Path(second["chunks_path"]),
    )
    texts = [chunk.text for chunk in store.list_chunks()]

    assert sorted(texts) == ["alpha", "beta", "delta", "gamma"]
    assert len(texts) == len(set(texts)), "previous vectors must not be duplicated"


@pytest.mark.integration
def test_failed_publish_rolls_back_to_the_previous_snapshot(monkeypatch):
    session_id = sessions.create_session("rollback pipeline")["id"]
    document = _seed(session_id, ["alpha", "beta"])
    first = indexing.build_candidate_snapshot(session_id, document["id"])
    first_ready = indexing.commit_ready_snapshot(session_id, first["id"], document["id"], 2)

    second_document = _seed(session_id, ["gamma"])
    second = indexing.build_candidate_snapshot(session_id, second_document["id"])

    def _fail(*_args, **_kwargs):
        raise RuntimeError("publish failed")

    monkeypatch.setattr(indexing.document_repo, "update_document_status", _fail)

    with pytest.raises(RuntimeError, match="publish failed"):
        indexing.commit_ready_snapshot(session_id, second["id"], second_document["id"], 3)

    assert snapshot_repo.get_snapshot(second["id"])["status"] == "failed"
    active = snapshot_repo.get_active_ready_snapshot(session_id)
    assert active["id"] == first["id"]
    assert index_repo.get_index(session_id)["index_path"] == first_ready["index_path"]


@pytest.mark.integration
def test_build_failure_is_reported_and_never_promoted(monkeypatch):
    session_id = sessions.create_session("build failure")["id"]
    document = _seed(session_id, ["alpha"])

    def _fail_save(self, index_path, chunks_path):
        raise OSError("disk full")

    monkeypatch.setattr(FAISSVectorStore, "save", _fail_save)

    with pytest.raises(SnapshotCommitError):
        indexing.build_candidate_snapshot(session_id, document["id"])

    assert snapshot_repo.get_active_ready_snapshot(session_id) is None
    assert document_repo.get_document(document["id"])["status"] == "uploaded"


@pytest.mark.integration
def test_rebuild_after_delete_drops_the_removed_documents_chunks():
    session_id = sessions.create_session("rebuild")["id"]
    first_document = _seed(session_id, ["alpha", "beta"])
    second_document = _seed(session_id, ["gamma"])
    candidate = indexing.build_candidate_snapshot(session_id, first_document["id"])
    indexing.commit_ready_snapshot(session_id, candidate["id"], first_document["id"], 3)

    chunk_repo.delete_chunks_for_document(second_document["id"])
    rebuilt = indexing.rebuild_session_snapshot(session_id)

    assert rebuilt is not None
    store = FAISSVectorStore.load(
        index_path=Path(rebuilt["index_path"]),
        chunks_path=Path(rebuilt["chunks_path"]),
    )
    assert sorted(chunk.text for chunk in store.list_chunks()) == ["alpha", "beta"]
