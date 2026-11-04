"""Composition root: the only place that turns configuration into capabilities.

Modules that need an LLM or an embedder ask this package instead of importing
a global singleton, so the heavy dependencies stay behind a single seam.
"""

import hashlib
import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from backend.domain.ports import Embedder, TextCompleter

if TYPE_CHECKING:
    from backend.domain.models import Chunk
    from backend.domain.ports import Reranker


class LlmTextCompleter:
    """TextCompleter over either the process-wide client or a per-user client."""

    def __init__(self, client=None) -> None:
        self._client = client

    def complete(self, prompt: str) -> str:
        if self._client is not None:
            return self._client.complete(prompt)
        from backend.adapters.llm.llm import complete_text

        return complete_text(prompt)

    def stream(self, prompt: str):
        if self._client is not None:
            return self._client.stream(prompt)
        from backend.adapters.llm.llm import stream_completion_tokens

        return stream_completion_tokens(prompt)

    @property
    def last_usage(self) -> dict | None:
        if self._client is not None:
            return self._client.last_usage
        from backend.adapters.llm.llm import last_usage

        return last_usage()

    @property
    def model(self) -> str | None:
        if self._client is not None:
            return self._client.model_name
        from backend.config import settings

        return settings.deepseek_model


@lru_cache(maxsize=1)
def text_completer() -> TextCompleter:
    """Process-wide text completer (the LLM client is already cached inside)."""
    return LlmTextCompleter()


_user_completers: dict[str, tuple[str, LlmTextCompleter]] = {}
_user_completers_lock = threading.Lock()


def user_text_completer(user_id: str | None) -> TextCompleter:
    """Per-user completer; cache key includes a hash of the effective config."""
    from backend.adapters.llm.model_client import ModelClient, ProviderConfig
    from backend.application.model_settings.service import resolve_llm

    config = resolve_llm(user_id)
    signature = hashlib.sha256(
        f"{config.provider}|{config.model}|{config.base_url}|{config.api_key}".encode()
    ).hexdigest()
    key = user_id or ""
    with _user_completers_lock:
        cached = _user_completers.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]
        provider = ProviderConfig(
            name=config.provider,
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            priority=1,
        )
        completer = LlmTextCompleter(ModelClient([provider]))
        _user_completers[key] = (signature, completer)
        return completer


def parser_chain(
    *,
    document_id: str | None = None,
    resume_batch_id: str | None = None,
    on_batch_created: Callable[[str], None] | None = None,
) -> list:
    """Ordered parser fallbacks: MinerU cloud (if key) -> local MinerU -> text PDF."""
    from backend.config import settings
    from backend.adapters.parsers.mineru_api_backend import MinerUApiBackend
    from backend.adapters.parsers.mineru_backend import MinerUBackend
    from backend.adapters.parsers.text_pdf_backend import TextPDFBackend

    if settings.mineru_require_cloud and not settings.mineru_api_key:
        raise RuntimeError("MINERU_REQUIRE_CLOUD=true requires MINERU_API_KEY")

    backends = [MinerUBackend(), TextPDFBackend()]
    if settings.mineru_api_key:
        backends.insert(
            0,
            MinerUApiBackend(
                document_id=document_id,
                resume_batch_id=resume_batch_id,
                on_batch_created=on_batch_created,
            ),
        )
    return backends


@lru_cache(maxsize=1)
def embedder() -> Embedder:
    """Process-wide embedder (remote -> local fallback chain)."""
    from backend.adapters.embedding import create_embed_fn

    return create_embed_fn()


@dataclass(frozen=True)
class ConfiguredEmbedding:
    """Effective embedder plus the signature of the index it can serve."""

    fingerprint: str
    cache_key: str
    mode: str
    model: str
    dim: int | None
    embed: Embedder


_user_embeddings: dict[str, tuple[str, ConfiguredEmbedding]] = {}
_user_embeddings_lock = threading.Lock()


def user_embedding(user_id: str | None) -> ConfiguredEmbedding:
    """Per-user embedder; cache key includes the effective endpoint and key."""
    from backend.application.model_settings.service import resolve_embedding

    config = resolve_embedding(user_id)
    signature = hashlib.sha256(
        f"{config.fingerprint}|{config.base_url}|{config.api_key}".encode()
    ).hexdigest()
    key = user_id or ""
    with _user_embeddings_lock:
        cached = _user_embeddings.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]

    if config.mode == "remote":
        from backend.adapters.embedding import remote_embedder

        def _embed(texts: list[str]) -> list[list[float]]:
            return remote_embedder.embed_with_config(
                texts,
                model=config.model,
                base_url=config.base_url,
                api_key=config.api_key,
            )

    else:
        from backend.adapters.embedding import local_embedder

        _embed = local_embedder.embed

    runtime = ConfiguredEmbedding(
        fingerprint=config.fingerprint,
        cache_key=signature,
        mode=config.mode,
        model=config.model,
        dim=config.dim,
        embed=_embed,
    )
    with _user_embeddings_lock:
        _user_embeddings[key] = (signature, runtime)
    return runtime


class ConfiguredReranker:
    """Reranker bound to a resolved provider; falls back only when allowed."""

    def __init__(self, config, fallback: "Reranker | None" = None) -> None:
        self._config = config
        self._fallback = fallback

    def rerank(self, query: str, chunks: list["Chunk"], top_k: int) -> list["Chunk"]:
        from backend.adapters.rerank import remote_reranker

        result = remote_reranker.rerank_with_config(
            query,
            chunks,
            top_k,
            model=self._config.model,
            base_url=self._config.base_url,
            api_key=self._config.api_key,
        )
        if result is not None:
            return result
        if self._fallback is not None:
            return self._fallback.rerank(query, chunks, top_k)
        return chunks[:top_k]


_user_rerankers: dict[str, tuple[str, "Reranker | None"]] = {}
_user_rerankers_lock = threading.Lock()


def user_reranker(user_id: str | None) -> "Reranker | None":
    """Per-user reranker; falls back to the env chain when the env key is used."""
    from backend.application.model_settings.service import resolve_rerank

    config = resolve_rerank(user_id)
    if not config.enabled:
        return None

    signature = hashlib.sha256(
        f"{config.mode}|{config.provider}|{config.model}|{config.base_url}|"
        f"{config.api_key}".encode()
    ).hexdigest()
    key = user_id or ""
    with _user_rerankers_lock:
        cached = _user_rerankers.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]

    if config.mode == "remote":
        fallback = None
        if config.key_source == "env":
            from backend.adapters.rerank.reranker import get_reranker

            fallback = get_reranker()
        reranker: "Reranker | None" = ConfiguredReranker(config, fallback)
    else:
        from backend.adapters.rerank.reranker import get_reranker

        reranker = get_reranker()

    with _user_rerankers_lock:
        _user_rerankers[key] = (signature, reranker)
    return reranker
