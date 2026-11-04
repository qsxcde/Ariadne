"""Font-aware heading repair for parser blocks."""

import pytest

from backend.domain.parsing import RawParserResult
from backend.rag.ingestion.typography import (
    CharSpan,
    PageTypography,
    _numbering_level,
    apply_pdf_typography,
)

PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0


def _top_bbox_span(
    text: str,
    bbox: dict[str, float],
    *,
    size: float,
    bold: bool = False,
) -> CharSpan:
    """Build a span whose box matches a top-left-origin normalized block bbox."""
    fontname = "TimesNewRomanPS-BoldMT" if bold else "TimesNewRomanPSMT"
    return CharSpan(
        text=text,
        fontname=fontname,
        size=size,
        x0=bbox["x0"] * PAGE_WIDTH,
        y0=(1.0 - bbox["y1"]) * PAGE_HEIGHT,
        x1=bbox["x1"] * PAGE_WIDTH,
        y1=(1.0 - bbox["y0"]) * PAGE_HEIGHT,
    )


def _block(block_type: str, text: str, bbox: dict[str, float]) -> dict:
    return {"type": block_type, "text": text, "bbox": bbox}


def _run(blocks: list[dict], spans: list[CharSpan]) -> RawParserResult:
    raw = RawParserResult(
        markdown="",
        page_count=1,
        pages=[
            {
                "page_number": 1,
                "width": 1.0,
                "height": 1.0,
                "blocks": blocks,
            }
        ],
        bbox_unit="normalized_1",
    )
    typography = {1: PageTypography(width=PAGE_WIDTH, height=PAGE_HEIGHT, spans=spans)}
    return apply_pdf_typography(raw, b"", loader=lambda _: typography)


def _body_span() -> CharSpan:
    return _top_bbox_span(
        "body " * 80,
        {"x0": 0.05, "y0": 0.6, "x1": 0.95, "y1": 0.9},
        size=10.0,
    )


@pytest.mark.unit
def test_bold_short_block_is_promoted_to_heading():
    bbox = {"x0": 0.1, "y0": 0.2, "x1": 0.35, "y1": 0.23}
    raw = _run(
        [_block("paragraph", "Related Work", bbox)],
        [_top_bbox_span("Related Work", bbox, size=12.0, bold=True), _body_span()],
    )

    block = raw.pages[0]["blocks"][0]
    assert block["type"] == "heading"
    assert block["heading_level"] == 1


@pytest.mark.unit
def test_bold_run_in_lead_stays_paragraph():
    bbox = {"x0": 0.1, "y0": 0.3, "x1": 0.6, "y1": 0.33}
    bold_part = {"x0": 0.1, "y0": 0.3, "x1": 0.25, "y1": 0.33}
    raw = _run(
        [_block("paragraph", "Methods We propose a framework", bbox)],
        [
            _top_bbox_span("Methods ", bold_part, size=10.0, bold=True),
            _top_bbox_span("We propose a framework", bbox, size=10.0),
            _body_span(),
        ],
    )

    assert raw.pages[0]["blocks"][0]["type"] == "paragraph"


@pytest.mark.unit
def test_margin_block_is_not_promoted():
    bbox = {"x0": 0.1, "y0": 0.02, "x1": 0.35, "y1": 0.05}
    raw = _run(
        [_block("paragraph", "Running Head", bbox)],
        [_top_bbox_span("Running Head", bbox, size=12.0, bold=True), _body_span()],
    )

    assert raw.pages[0]["blocks"][0]["type"] == "paragraph"


@pytest.mark.unit
def test_numbered_heading_uses_numbering_depth():
    bbox = {"x0": 0.1, "y0": 0.4, "x1": 0.35, "y1": 0.43}
    raw = _run(
        [_block("paragraph", "2.1 Dataset", bbox)],
        [_top_bbox_span("2.1 Dataset", bbox, size=11.0, bold=True), _body_span()],
    )

    assert raw.pages[0]["blocks"][0]["heading_level"] == 2


@pytest.mark.unit
def test_parser_heading_levels_are_corrected_by_numbering():
    bbox = {"x0": 0.1, "y0": 0.1, "x1": 0.4, "y1": 0.13}
    raw = _run(
        [_block("title", "I. INTRODUCTION", bbox)],
        [_top_bbox_span("I. INTRODUCTION", bbox, size=10.0), _body_span()],
    )

    block = raw.pages[0]["blocks"][0]
    assert block["type"] == "title"
    assert block["heading_level"] == 1


@pytest.mark.unit
def test_numbering_styles_for_academic_sections():
    assert _numbering_level("I. INTRODUCTION") == 1
    assert _numbering_level("A. Attention-Based MIL") == 2
    assert _numbering_level("1) Sparse Feature Gating") == 3
    assert _numbering_level("a) Detail") == 4
    assert _numbering_level("Related Work") is None
