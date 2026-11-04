"""Chunk budgets are measured in estimated tokens, never in characters."""

import pytest

from backend.rag.ingestion.chunking import (
    _recursive_split,
    build_chunks,
    estimate_tokens,
    token_length,
)
from backend.rag.ingestion.document_ir import (
    BBox,
    BlockIR,
    DocumentIR,
    PageIR,
    QualityReport,
)


@pytest.mark.unit
def test_token_length_is_continuous_and_empty_for_no_text():
    assert token_length("") == 0.0
    assert token_length("x" * 400) == pytest.approx(100.0)
    assert estimate_tokens("") == 0


@pytest.mark.unit
def test_hard_split_keeps_every_piece_within_the_token_budget():
    pieces = _recursive_split("x" * 20_000, max_tokens=100, overlap_tokens=20)

    assert len(pieces) > 1
    assert all(token_length(piece) <= 100 for piece in pieces)


@pytest.mark.unit
def test_cjk_is_budgeted_by_tokens_not_characters():
    pieces = _recursive_split("中" * 3_000, max_tokens=100, overlap_tokens=0)

    assert len(pieces) > 1
    assert all(token_length(piece) <= 100 for piece in pieces)
    # 100 tokens of CJK is roughly 150 characters; a character budget would
    # have produced 30 pieces instead.
    assert len(pieces) < 30


@pytest.mark.unit
def test_adjacent_chunks_share_the_configured_overlap():
    body = " ".join(f"token{index}" for index in range(2_000))

    pieces = _recursive_split(body, max_tokens=50, overlap_tokens=10)

    assert len(pieces) > 1
    assert set(pieces[0].split()) & set(pieces[1].split())


@pytest.mark.unit
def test_build_chunks_respects_the_configured_token_budget():
    body = "sentence without punctuation " * 500
    document = DocumentIR(
        document_id="doc-1",
        filename="budget.pdf",
        page_count=1,
        parser_name="test",
        parser_version="1",
        pages=[
            PageIR(
                page_number=1,
                width=1,
                height=1,
                rotation=0,
                blocks=[
                    BlockIR(
                        id="b-1",
                        page_number=1,
                        block_index=0,
                        type="paragraph",
                        text=body,
                        bbox=BBox(x0=0, y0=0, x1=1, y1=1),
                        reading_order=0,
                        section_path=["1"],
                    )
                ],
            )
        ],
        quality_report=QualityReport(
            parser_name="test", parser_version="1", page_count=1
        ),
    )

    chunks = build_chunks(document, "", "doc-1", max_tokens=200, overlap_tokens=20)

    assert len(chunks) > 1
    # The heading prefix adds a few tokens on top of the body budget.
    assert all(estimate_tokens(chunk.text) <= 260 for chunk in chunks)
