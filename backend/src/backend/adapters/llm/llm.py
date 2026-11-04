"""LLM client wrapper — delegates to ModelClient for multi-provider fallback.

Public API (unchanged):
    complete_text(prompt) -> str
    stream_completion_tokens(prompt) -> Generator[str]
"""
from __future__ import annotations

import logging
from collections.abc import Generator

from backend.config import require_generation_settings
from backend.adapters.llm.model_client import ModelClient, build_providers
from backend.adapters.resources import LazyResource

logger = logging.getLogger(__name__)


def _build_client() -> ModelClient:
    require_generation_settings()
    client = ModelClient(build_providers())
    logger.info("Initialized ModelClient with %d provider(s)", client.provider_count)
    return client


_client: LazyResource[ModelClient] = LazyResource(_build_client)


def _get_client() -> ModelClient:
    return _client.get()


def complete_text(prompt: str) -> str:
    """Synchronous LLM completion. Delegates to ModelClient with fallback."""
    return _get_client().complete(prompt)


def stream_completion_tokens(prompt: str) -> Generator[str, None, None]:
    """Streaming LLM completion. Delegates to ModelClient with fallback."""
    return _get_client().stream(prompt)


def last_usage() -> dict | None:
    """Token usage reported by the last completed stream, if any.

    Reads the cached client without triggering a build, so callers that only
    report usage never initialise the LLM stack.
    """
    client = _client.value
    return client.last_usage if client is not None else None
