"""Cross-layer domain models shared by storage, RAG, and the HTTP layer.

Data contracts only — behavior belongs to the layer that owns it.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


BBoxUnit = Literal["points", "normalized_1000", "normalized_1"]

ChunkType = Literal[
    "abstract", "paragraph", "table", "heading", "formula", "code", "caption", "reference"
]


class ChunkMetadata(BaseModel):
    paper_id: str
    section: str
    chunk_index: int
    type: ChunkType
    section_path: list[str] | None = None
    page_start: int | None = None
    page_end: int | None = None
    bbox: dict[str, float] | None = None
    block_ids: list[str] | None = None
    block_types: list[str] | None = None
    linked_block_ids: list[str] | None = None
    confidence: float | None = None
    word_count: int | None = None
    char_count: int | None = None
    is_reference: bool = False


class Chunk(BaseModel):
    text: str
    metadata: ChunkMetadata


@dataclass(frozen=True, slots=True)
class VectorSearchHit:
    """A dense-search result: chunk, distance score and 1-based rank."""

    chunk: Chunk
    score: float
    rank: int


class SourceRef(BaseModel):
    paper_id: str | None = None
    section: str
    chunk_index: int
    text_excerpt: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    block_ids: list[str] | None = None
    confidence: float | None = None
