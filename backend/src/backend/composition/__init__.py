"""Composition root: the only place that turns configuration into capabilities.

Modules that need an LLM or an embedder ask this package instead of importing
a global singleton, so the heavy dependencies stay behind a single seam.
"""

from collections.abc import Callable
from functools import lru_cache

from backend.core.contracts.ports import Embedder, TextCompleter


class LlmTextCompleter:
    """Adapter over the existing multi-provider LLM client."""

    def complete(self, prompt: str) -> str:
        from backend.adapters.llm.llm import complete_text

        return complete_text(prompt)

    def stream(self, prompt: str):
        from backend.adapters.llm.llm import stream_completion_tokens

        return stream_completion_tokens(prompt)


@lru_cache(maxsize=1)
def text_completer() -> TextCompleter:
    """Process-wide text completer (the LLM client is already cached inside)."""
    return LlmTextCompleter()


def parser_chain(
    *,
    document_id: str | None = None,
    resume_batch_id: str | None = None,
    on_batch_created: Callable[[str], None] | None = None,
) -> list:
    """Ordered parser fallbacks: MinerU cloud (if key) -> local MinerU -> text PDF."""
    from backend.config import settings
    from backend.rag.ingestion.mineru_api_backend import MinerUApiBackend
    from backend.rag.ingestion.mineru_backend import MinerUBackend
    from backend.rag.ingestion.text_pdf_backend import TextPDFBackend

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
