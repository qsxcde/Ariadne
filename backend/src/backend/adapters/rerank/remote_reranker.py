"""Remote reranker via SiliconFlow / OpenAI-compatible rerank API."""
import logging
import threading
import time

import httpx

from backend.config import settings
from backend.domain.models import Chunk
from backend.adapters.resources import LazyResource

logger = logging.getLogger(__name__)


def _create_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.reranker_remote_base_url,
        headers={
            "Authorization": f"Bearer {settings.embedding_remote_api_key}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )


_client: LazyResource[httpx.Client] = LazyResource(_create_client)
_clients: dict[tuple[str, str], httpx.Client] = {}
_clients_lock = threading.Lock()


def _get_client() -> httpx.Client:
    return _client.get()


def _client_for(base_url: str, api_key: str) -> httpx.Client:
    key = (base_url, api_key)
    with _clients_lock:
        client = _clients.get(key)
        if client is None:
            client = httpx.Client(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            _clients[key] = client
        return client


def rerank(query: str, chunks: list[Chunk], top_k: int) -> list[Chunk] | None:
    """Rerank chunks via SiliconFlow rerank API. Returns None on failure."""
    return rerank_with_config(
        query,
        chunks,
        top_k,
        model=settings.reranker_remote_model,
        base_url=settings.reranker_remote_base_url,
        api_key=settings.embedding_remote_api_key or "",
    )


def rerank_with_config(
    query: str,
    chunks: list[Chunk],
    top_k: int,
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> list[Chunk] | None:
    """Rerank with an explicit provider config (per-user settings)."""
    if not chunks or not api_key:
        return None

    client = _client_for(base_url, api_key)
    documents = [c.text for c in chunks]

    start = time.monotonic()
    logger.info(
        "Reranking %d chunks via remote API model=%s",
        len(documents), model,
    )

    try:
        resp = client.post(
            "/rerank",
            json={
                "model": model,
                "query": query,
                "documents": documents,
                "top_n": top_k,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        indices = [r["index"] for r in results]
        reranked = [chunks[i] for i in indices if i < len(chunks)]
        logger.info(
            "Reranked %d chunks via remote API elapsed=%.2fs",
            len(reranked), time.monotonic() - start,
        )
        return reranked
    except Exception:
        logger.warning("Remote reranker failed", exc_info=True)
        return None
