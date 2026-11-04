"""Structured logging for LLM generations (tokens + latency)."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("backend.generation")


@contextmanager
def generation_timer(
    operation: str, *, paper_id: str | None = None
) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        from backend.adapters.llm.llm import last_usage

        usage = last_usage() or {}
        logger.info(
            "llm_generation operation=%s paper_id=%s elapsed_ms=%.1f prompt_tokens=%s completion_tokens=%s",
            operation,
            paper_id,
            (time.perf_counter() - started) * 1000,
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
