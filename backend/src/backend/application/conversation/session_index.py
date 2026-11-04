"""Resolve the active retrieval index of a session, waiting for it if needed."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable

from backend.adapters.vector import store_cache
from backend.application.model_settings.service import env_embedding_fingerprint
from backend.domain.ports import EmbeddingRuntime, VectorStore
from backend.storage.records import SnapshotRecord
from backend.config import settings
from backend.domain.exceptions import (
    ActiveIndexNotReadyError,
    IndexEmbeddingMismatchError,
    SessionNotFoundError,
)
from backend.storage.sqlite import index_snapshots as snapshot_repo
from backend.storage.sqlite import sessions as session_repo


async def resolve_session_store(
    session_id: str,
    wait_timeout_seconds: float | None = None,
    on_wait_for_index: Callable[[], None] | None = None,
    embedding: EmbeddingRuntime | None = None,
) -> tuple[VectorStore, bool]:
    if wait_timeout_seconds is None:
        wait_timeout_seconds = settings.index_max_wait

    session = await asyncio.to_thread(session_repo.get_session, session_id)
    if session is None or session["is_archived"]:
        raise SessionNotFoundError(f"Session not found: {session_id}", session_id=session_id)

    ready_snapshot = await asyncio.to_thread(snapshot_repo.get_active_ready_snapshot, session_id)
    waited_for_index = False
    if ready_snapshot is None:
        waited_for_index = True
        if on_wait_for_index is not None:
            on_wait_for_index()
        ready_snapshot = await wait_for_ready_index(
            session_id,
            timeout_seconds=wait_timeout_seconds,
        )
        if ready_snapshot is None:
            raise ActiveIndexNotReadyError(
                "索引尚未就绪", session_id=session_id
            )

    if embedding is not None:
        stored = ready_snapshot.get("embedding_fingerprint")
        if (stored or env_embedding_fingerprint()) != embedding.fingerprint:
            raise IndexEmbeddingMismatchError(
                settings.msg_index_embedding_stale, session_id=session_id
            )

    return store_cache.get_store_for_snapshot(
        ready_snapshot, embedding=embedding
    ), waited_for_index


async def wait_for_ready_index(
    session_id: str, timeout_seconds: float
) -> SnapshotRecord | None:
    deadline = time.monotonic() + timeout_seconds
    backoff = settings.index_poll_interval
    while time.monotonic() < deadline:
        ready_snapshot = await asyncio.to_thread(
            snapshot_repo.get_active_ready_snapshot, session_id
        )
        if ready_snapshot is not None:
            return ready_snapshot
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, settings.index_poll_max_interval)
    raise ActiveIndexNotReadyError(settings.msg_index_not_ready, session_id=session_id)
