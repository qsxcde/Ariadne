from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from cachetools import LRUCache

from backend.storage.records import SnapshotRecord
from backend.domain.states import PROCESSING_DOCUMENT_STAGES
from backend.rag.retrieval.filters import filter_indexable_chunks

if TYPE_CHECKING:
    from backend.adapters.vector.faiss_store import FAISSVectorStore
    from backend.domain.ports import EmbeddingRuntime
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import index_snapshots as snapshot_repo
from backend.storage.sqlite import indexes as index_repo

_MAX_CACHED_STORES = 16
# Guarded by ``_store_lock``: cachetools itself is not thread-safe.
_stores: "LRUCache[str, tuple[str, FAISSVectorStore]]" = LRUCache(
    maxsize=_MAX_CACHED_STORES
)
_store_lock = threading.RLock()


def _cache_store(session_id: str, cache_key: str, store: FAISSVectorStore) -> None:
    """Insert into the LRU cache; cachetools evicts the oldest entry when full."""
    _stores[session_id] = (cache_key, store)


def _new_store(embedding: "EmbeddingRuntime | None" = None) -> FAISSVectorStore:
    """Import FAISS lazily so importing this module stays dependency-light."""
    from backend.adapters.vector.faiss_store import FAISSVectorStore

    if embedding is None:
        return FAISSVectorStore()
    return FAISSVectorStore(
        embed_fn=embedding.embed, embedding_dim=embedding.dim
    )


def _load_store(
    index_path: Path,
    chunks_path: Path,
    embedding: "EmbeddingRuntime | None" = None,
) -> FAISSVectorStore:
    from backend.adapters.vector.faiss_store import FAISSVectorStore

    return FAISSVectorStore.load(
        index_path=index_path,
        chunks_path=chunks_path,
        embed_fn=embedding.embed if embedding is not None else None,
    )


def get_store(
    session_id: str, *, embedding: "EmbeddingRuntime | None" = None
) -> FAISSVectorStore:
    cache_suffix = embedding.cache_key if embedding is not None else "default"
    with _store_lock:
        metadata = index_repo.get_index(session_id)
        if metadata and metadata["status"] == "ready":
            cache_key = f"legacy:{metadata['updated_at']}:{cache_suffix}"
            cached = _stores.get(session_id)
            if cached and cached[0] == cache_key:
                return cached[1]
            store = _load_store(
                Path(metadata["index_path"]),
                Path(metadata["chunks_path"]),
                embedding,
            )
            _cache_store(session_id, cache_key, store)
            return store

        ready_snapshot = snapshot_repo.get_active_ready_snapshot(session_id)
        if ready_snapshot is not None:
            return get_store_for_snapshot(ready_snapshot, embedding=embedding)

        existing_chunks = chunk_repo.list_chunks(session_id)
        session_documents = document_repo.list_documents(session_id)
        has_processing_documents = any(
            document["status"] in PROCESSING_DOCUMENT_STAGES
            for document in session_documents
        )
        if existing_chunks and not has_processing_documents:
            store = _new_store(embedding)
            store.add_chunks(filter_indexable_chunks(existing_chunks))
            return store

        store = _new_store(embedding)
        _cache_store(session_id, f"empty:{cache_suffix}", store)
        return store


def discard_store(session_id: str) -> None:
    with _store_lock:
        _stores.pop(session_id, None)


def get_store_for_snapshot(
    snapshot: SnapshotRecord, *, embedding: "EmbeddingRuntime | None" = None
) -> FAISSVectorStore:
    session_id = snapshot["session_id"]
    cache_suffix = embedding.cache_key if embedding is not None else "default"
    cache_key = f"snapshot:{snapshot['id']}:{snapshot['updated_at']}:{cache_suffix}"
    with _store_lock:
        cached = _stores.get(session_id)
        if cached and cached[0] == cache_key:
            return cached[1]
        store = _load_store(
            Path(snapshot["index_path"]),
            Path(snapshot["chunks_path"]),
            embedding,
        )
        _cache_store(session_id, cache_key, store)
        return store
