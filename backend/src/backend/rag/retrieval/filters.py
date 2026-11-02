from backend.domain.models import Chunk


REFERENCE_SECTION_NAMES = {
    "references", "reference", "bibliography", "参考文献",
    "literaturverzeichnis", "bibliographie", "referencias",
    "참고문헌", "参考文獻",
}


def is_reference_chunk(chunk: Chunk) -> bool:
    """Return whether a chunk belongs to the paper bibliography section."""
    if chunk.metadata.is_reference:
        return True
    labels = [chunk.metadata.section, *(chunk.metadata.section_path or [])]
    return any(_normalize_section_label(label) in REFERENCE_SECTION_NAMES for label in labels)


def filter_indexable_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """Keep chunks that should participate in default paper QA retrieval."""
    return [chunk for chunk in chunks if not is_reference_chunk(chunk)]


def chunk_matches_scope(
    chunk: Chunk,
    *,
    document_ids: list[str] | None = None,
    section: str | None = None,
    chunk_types: list[str] | None = None,
) -> bool:
    """Return whether a chunk is inside the requested paper/section/type scope."""
    if document_ids and chunk.metadata.paper_id not in set(document_ids):
        return False
    if section:
        labels = [chunk.metadata.section, *(chunk.metadata.section_path or [])]
        wanted = section.strip().lower()
        if not any(wanted in label.strip().lower() for label in labels if label):
            return False
    if chunk_types and chunk.metadata.type not in set(chunk_types):
        return False
    return True


def filter_chunks_by_scope(
    chunks: list[Chunk],
    *,
    document_ids: list[str] | None = None,
    section: str | None = None,
    chunk_types: list[str] | None = None,
) -> list[Chunk]:
    return [
        chunk
        for chunk in chunks
        if chunk_matches_scope(
            chunk,
            document_ids=document_ids,
            section=section,
            chunk_types=chunk_types,
        )
    ]


def _normalize_section_label(label: str | None) -> str:
    if label is None:
        return ""
    normalized = " ".join(label.strip().lower().split())
    while normalized and (normalized[0].isdigit() or normalized[0] in ".、)）"):
        normalized = normalized[1:].strip()
    return normalized
