from __future__ import annotations

from collections.abc import Iterable
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.rag.ingestion.document_ir import BBox, BlockIR, DocumentIR
from backend.rag.ingestion.render import ordered_blocks, render_block
from backend.domain.models import Chunk, ChunkMetadata, ChunkType


# Every budget in this module is measured in *estimated tokens* (see
# ``estimate_tokens``); nothing here is a character count.
DEFAULT_MAX_TOKENS = 2000
DEFAULT_OVERLAP_TOKENS = 120
SEPARATORS = ["\n\n", "\n", ". ", "。", "！", "？", " ", ""]
MERGEABLE_TYPES = {"paragraph", "figure_caption", "table_caption", "reference"}


# One token is 12 units: ASCII costs 3 units/char (~4 chars per token) and CJK
# costs 8 units/char (~1.5 chars per token). Everything stays integer so the
# splitter's overlap subtraction is exact while per-character granularity
# survives; float lengths leave dust behind and walk off the list.
UNITS_PER_TOKEN = 12


def token_units(text: str) -> int:
    """Token count scaled by :data:`UNITS_PER_TOKEN` (the splitter's unit)."""
    cjk = sum(1 for c in text if "一" <= c <= "鿿" or 0x3400 <= ord(c) <= 0x4DBF)
    other = len(text) - cjk
    return other * 3 + cjk * 8


def token_length(text: str) -> float:
    """Continuous token estimate: English ~1/4 char, CJK ~1/1.5 char."""
    return token_units(text) / UNITS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    """Integer token count for budgets and reporting (0 for empty text)."""
    if not text:
        return 0
    return max(1, token_units(text) // UNITS_PER_TOKEN)


def build_chunks(
    document_ir: DocumentIR,
    markdown: str,
    paper_id: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    if not ordered_blocks(document_ir):
        return _build_markdown_only_chunks(
            markdown,
            paper_id,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )

    chunks: list[Chunk] = []
    text_buffer: list[BlockIR] = []

    def flush_text_buffer() -> None:
        nonlocal text_buffer
        if not text_buffer:
            return
        section_path = _section_path(text_buffer[0])
        body = "\n\n".join(render_block(block) for block in text_buffer if block.text.strip()).strip()
        block_ids = [block.id for block in text_buffer]
        block_types = _unique(block.type for block in text_buffer)
        linked_block_ids = _linked_block_ids(text_buffer)
        confidence = min(block.confidence for block in text_buffer)
        bbox = _merge_bboxes([block.bbox for block in text_buffer]).model_dump()
        page_start = min(block.page_number for block in text_buffer)
        page_end = max(block.page_number for block in text_buffer)
        is_reference = _is_reference_section(section_path)
        chunk_type: ChunkType = "reference" if is_reference else _chunk_type(text_buffer[0])
        for part in _recursive_split(
            body, max_tokens=max_tokens, overlap_tokens=overlap_tokens
        ):
            _append_chunk(
                chunks,
                paper_id=paper_id,
                section_path=section_path,
                body=part,
                chunk_type=chunk_type,
                block_ids=block_ids,
                block_types=block_types,
                linked_block_ids=linked_block_ids,
                confidence=confidence,
                bbox=bbox,
                page_start=page_start,
                page_end=page_end,
                is_reference=is_reference,
            )
        text_buffer = []

    for block in ordered_blocks(document_ir):
        if block.type in {"title", "heading", "header_footer", "figure"}:
            continue
        if _is_code_block(block):
            flush_text_buffer()
            _append_single_block_chunk(chunks, paper_id, block, "code")
            continue
        if block.type == "reference":
            flush_text_buffer()
            _append_single_block_chunk(chunks, paper_id, block, "reference")
            continue
        if block.type in MERGEABLE_TYPES:
            if text_buffer and _section_path(text_buffer[0]) != _section_path(block):
                flush_text_buffer()
            text_buffer.append(block)
            continue
        flush_text_buffer()
        _append_single_block_chunk(chunks, paper_id, block, _chunk_type(block))
    flush_text_buffer()
    return chunks


def _build_markdown_only_chunks(
    markdown: str,
    paper_id: str,
    *,
    max_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    section_path = ["Document"]
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n\n".join(part.strip() for part in buffer if part.strip()).strip()
        buffer = []
        if not body:
            return
        is_reference = _is_reference_section(section_path)
        chunk_type: ChunkType = (
            "reference"
            if is_reference
            else ("abstract" if section_path[-1].lower() == "abstract" else "paragraph")
        )
        for part in _recursive_split(
            body, max_tokens=max_tokens, overlap_tokens=overlap_tokens
        ):
            _append_chunk(
                chunks,
                paper_id=paper_id,
                section_path=section_path,
                body=part,
                chunk_type=chunk_type,
                block_ids=[],
                block_types=["markdown"],
                linked_block_ids=None,
                confidence=0.5,
                bbox=None,
                page_start=None,
                page_end=None,
                is_reference=is_reference,
            )

    for raw_line in markdown.strip().splitlines():
        line = raw_line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip() or "Document"
            parent = section_path[: max(level - 1, 0)]
            section_path = [*parent, title] if parent else [title]
            continue
        if not line:
            flush()
            continue
        buffer.append(line)
    flush()
    if not chunks:
        _append_chunk(
            chunks,
            paper_id=paper_id,
            section_path=["Document"],
            body=markdown.strip(),
            chunk_type="paragraph",
            block_ids=[],
            block_types=["markdown"],
            linked_block_ids=None,
            confidence=0.5,
            bbox=None,
            page_start=None,
            page_end=None,
            is_reference=False,
        )
    return chunks


def _section_path(block: BlockIR) -> list[str]:
    return block.section_path or ["Document"]


def _heading_prefix(section_path: list[str]) -> str:
    return "\n".join(f"{'#' * min(index + 2, 6)} {title}" for index, title in enumerate(section_path))


def _chunk_type(block: BlockIR) -> ChunkType:
    if block.type == "table":
        return "table"
    if block.type == "formula":
        return "formula"
    if block.type in {"figure_caption", "table_caption"}:
        return "caption"
    if _is_reference_section(_section_path(block)) or block.type == "reference":
        return "reference"
    section = _section_path(block)[-1].lower()
    return "abstract" if section == "abstract" else "paragraph"


def _is_code_block(block: BlockIR) -> bool:
    return block.text.strip().startswith("```")


def _is_reference_section(section_path: list[str]) -> bool:
    return any(part.strip().lower() in {"references", "bibliography"} for part in section_path)


def _append_single_block_chunk(
    chunks: list[Chunk], paper_id: str, block: BlockIR, chunk_type: ChunkType
) -> None:
    _append_chunk(
        chunks,
        paper_id=paper_id,
        section_path=_section_path(block),
        body=render_block(block),
        chunk_type=chunk_type,
        block_ids=[block.id],
        block_types=[block.type],
        linked_block_ids=_linked_block_ids([block]),
        confidence=block.confidence,
        bbox=block.bbox.model_dump(),
        page_start=block.page_number,
        page_end=block.page_number,
        is_reference=_is_reference_section(_section_path(block)) or block.type == "reference",
    )


def _append_chunk(
    chunks: list[Chunk],
    *,
    paper_id: str,
    section_path: list[str],
    body: str,
    chunk_type: ChunkType,
    block_ids: list[str],
    block_types: list[str],
    linked_block_ids: list[str] | None,
    confidence: float,
    bbox: dict[str, float] | None,
    page_start: int | None,
    page_end: int | None,
    is_reference: bool,
) -> None:
    body = body.strip()
    if not body:
        return
    text = f"{_heading_prefix(section_path)}\n\n{body}".strip()
    chunks.append(
        Chunk(
            text=text,
            metadata=ChunkMetadata(
                paper_id=paper_id,
                section=" > ".join(section_path),
                section_path=section_path,
                chunk_index=len(chunks),
                type=chunk_type,
                page_start=page_start,
                page_end=page_end,
                bbox=bbox,
                block_ids=block_ids,
                block_types=block_types,
                linked_block_ids=linked_block_ids,
                confidence=confidence,
                char_count=len(text),
                word_count=len(text.split()),
                is_reference=is_reference,
            ),
        )
    )


def _splitter(
    max_tokens: int, overlap_tokens: int
) -> RecursiveCharacterTextSplitter:
    """Tokenizer-aware recursive splitter; every length here is in token units."""
    size = max(1, max_tokens) * UNITS_PER_TOKEN
    # langchain requires chunk_overlap <= chunk_size.
    overlap = max(0, min(overlap_tokens, max_tokens - 1)) * UNITS_PER_TOKEN
    return RecursiveCharacterTextSplitter(
        separators=SEPARATORS,
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=token_units,
        keep_separator=False,
        strip_whitespace=True,
    )


def _recursive_split(
    text: str, *, max_tokens: int, overlap_tokens: int
) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if token_length(text) <= max_tokens:
        return [text]
    return _splitter(max_tokens, overlap_tokens).split_text(text)


def _merge_bboxes(bboxes: list[BBox]) -> BBox:
    return BBox(
        x0=min(bbox.x0 for bbox in bboxes),
        y0=min(bbox.y0 for bbox in bboxes),
        x1=max(bbox.x1 for bbox in bboxes),
        y1=max(bbox.y1 for bbox in bboxes),
    )


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _linked_block_ids(blocks: Iterable[BlockIR]) -> list[str] | None:
    ids = _unique(link.target_block_id for block in blocks for link in block.links)
    return ids or None
