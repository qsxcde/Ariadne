"""Section hierarchy accepts parser-reported levels and MinerU ``title`` blocks."""

import pytest

from backend.rag.ingestion.document_ir import BBox, BlockIR
from backend.rag.ingestion.section_builder import next_section_path, outline_from_blocks


def _block(block_type: str, text: str, *, level: int | None = None, order: int = 0) -> BlockIR:
    return BlockIR(
        id=f"b-{order}",
        page_number=1,
        block_index=order,
        type=block_type,  # type: ignore[arg-type]
        text=text,
        bbox=BBox(x0=0, y0=0, x1=1, y1=1),
        reading_order=order,
        section_path=[],
        heading_level=level,
    )


@pytest.mark.unit
def test_explicit_level_handles_roman_numeral_titles():
    assert next_section_path(["Abstract"], "I. INTRODUCTION", level=1) == ["I. INTRODUCTION"]


@pytest.mark.unit
def test_explicit_level_nests_under_parent():
    current = ["I. INTRODUCTION"]

    assert next_section_path(current, "A. Datasets", level=2) == ["I. INTRODUCTION", "A. Datasets"]


@pytest.mark.unit
def test_missing_parent_levels_are_filled():
    assert next_section_path([], "Deep heading", level=3) == ["Unknown", "Unknown", "Deep heading"]


@pytest.mark.unit
def test_numbering_heuristic_still_applies_without_level():
    assert next_section_path(["Intro"], "2.1 Method", level=None) == ["Intro", "Method"]


@pytest.mark.unit
def test_unnumbered_heading_without_level_replaces_leaf():
    assert next_section_path(["Paper", "Intro"], "Related Work", level=None) == [
        "Paper",
        "Related Work",
    ]


@pytest.mark.unit
def test_outline_counts_titles_and_headings():
    blocks = [
        _block("title", "Paper title", order=0),
        _block("heading", "1 Introduction", order=1),
        _block("paragraph", "body", order=2),
    ]

    assert outline_from_blocks(blocks) == ["Paper title", "1 Introduction"]
