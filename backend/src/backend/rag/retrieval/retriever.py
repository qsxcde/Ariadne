from backend.domain.models import Chunk
from backend.domain.ports import VectorStore
from backend.rag.retrieval.filters import filter_indexable_chunks


def retrieve_seed_chunks(
    store: VectorStore,
    question: str,
    k: int | None = None,
    *,
    default_k: int,
) -> list[Chunk]:
    resolved_k = k or default_k
    return filter_indexable_chunks(store.search(question, k=resolved_k))
