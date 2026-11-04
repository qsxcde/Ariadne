"""Remote embedding via OpenAI-compatible API (SiliconFlow / Gitee AI / etc.)."""
import logging
import threading
import time

from openai import OpenAI

from backend.config import settings
from backend.adapters.embedding.local_embedder import truncate_for_embedding
from backend.adapters.resources import LazyResource

logger = logging.getLogger(__name__)


def _create_client() -> OpenAI:
    return OpenAI(
        base_url=settings.embedding_remote_base_url,
        api_key=settings.embedding_remote_api_key,
        timeout=30,
    )


_client: LazyResource[OpenAI] = LazyResource(_create_client)
_clients: dict[tuple[str, str], OpenAI] = {}
_clients_lock = threading.Lock()


def _get_client() -> OpenAI:
    return _client.get()


def _client_for(base_url: str, api_key: str) -> OpenAI:
    key = (base_url, api_key)
    with _clients_lock:
        client = _clients.get(key)
        if client is None:
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=30)
            _clients[key] = client
        return client


def embed(texts: list[str]) -> list[list[float]]:
    """Embed texts via remote API (OpenAI-compatible)."""
    return embed_with_config(
        texts,
        model=settings.embedding_remote_model,
        base_url=settings.embedding_remote_base_url,
        api_key=settings.embedding_remote_api_key or "",
    )


def embed_with_config(
    texts: list[str],
    *,
    model: str,
    base_url: str,
    api_key: str,
) -> list[list[float]]:
    """Embed with an explicit provider config (per-user settings)."""
    client = _client_for(base_url, api_key)
    truncated = [truncate_for_embedding(t) for t in texts]

    start = time.monotonic()
    logger.info("Encoding %d texts with remote embedding model=%s", len(texts), model)

    resp = client.embeddings.create(
        model=model,
        input=truncated,
    )

    sorted_data = sorted(resp.data, key=lambda x: x.index)
    rows = [d.embedding for d in sorted_data]
    dimension = len(rows[0]) if rows else 0
    logger.info(
        "Encoded %d texts via remote API dimension=%d elapsed=%.2fs",
        len(rows), dimension, time.monotonic() - start,
    )
    return rows
