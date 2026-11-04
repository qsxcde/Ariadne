"""Use PDF font metadata to repair headings that layout parsers miss.

MinerU's VLM is good at reading order and formulas but sometimes labels short,
bold section titles as paragraphs, and it does not expose font weight at all.
This module reads the PDF text layer with pdfminer, matches character spans to
parser blocks by bounding box, and promotes blocks whose typography is clearly
heading-like (bold, larger than body text, short, no terminal punctuation).
"""

from __future__ import annotations

import io
import logging
import re
import statistics
from dataclasses import dataclass
from typing import Callable

from backend.domain.parsing import RawParserResult
from backend.rag.ingestion.block_classifier import NUMBERED_HEADING_PATTERN

logger = logging.getLogger(__name__)

_BOLD_FONT_PATTERN = re.compile(
    r"(bold|black|heavy|demi|semibold|cmbx)", re.IGNORECASE
)
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_TERMINAL_PUNCTUATION = (".", "。", ";", "；", ",", "，", "!", "！", "?", "？")
_ROMAN_HEADING = re.compile(r"^[IVX]+\.\s+")
_LETTER_HEADING = re.compile(r"^[A-Z]\.\s+")
_PAREN_DIGIT_HEADING = re.compile(r"^\d+\)\s+")
_PAREN_LETTER_HEADING = re.compile(r"^[a-z]\)\s+")

_NON_HEADING_TYPES = frozenset(
    {
        "title",
        "heading",
        "table",
        "table_caption",
        "figure",
        "figure_caption",
        "formula",
        "footnote",
        "reference",
        "header_footer",
    }
)


@dataclass(frozen=True)
class CharSpan:
    text: str
    fontname: str
    size: float
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class PageTypography:
    width: float
    height: float
    spans: list[CharSpan]


TypographyPages = dict[int, PageTypography]
TypographyLoader = Callable[[bytes], TypographyPages]


def apply_pdf_typography(
    raw: RawParserResult,
    pdf_bytes: bytes,
    *,
    loader: TypographyLoader | None = None,
) -> RawParserResult:
    """Enrich ``raw.pages`` block types in place; fail open on any PDF error."""
    try:
        pages = (loader or extract_pdf_typography)(pdf_bytes)
    except Exception as exc:
        logger.warning("PDF typography extraction failed; skipping heading repair: %s", exc)
        return raw
    if not pages:
        return raw

    body_size = _body_font_size(pages)
    promoted: list[tuple[dict, float, int | None]] = []

    for page_data in raw.pages:
        page_number = int(page_data.get("page_number") or 0)
        typography = pages.get(page_number)
        if typography is None:
            continue
        for block in page_data.get("blocks", []) or []:
            if not isinstance(block, dict):
                continue
            text = str(block.get("text", "")).strip()
            if str(block.get("type", "")).strip().lower() in {"title", "heading"}:
                # MinerU often emits one level for every heading; numbering
                # styles (I. / A. / 1)) are more reliable when present.
                numbering = _numbering_level(text)
                if numbering is not None:
                    block["heading_level"] = numbering
                continue
            if not _can_promote(block):
                continue
            if not _heading_length_ok(text) or text.endswith(_TERMINAL_PUNCTUATION):
                continue
            bbox = _block_bbox_normalized(block, typography, raw.bbox_unit)
            if bbox is None or _is_margin_box(bbox):
                continue
            features = _collect_features(
                typography.spans,
                bbox,
                typography.width,
                typography.height,
            )
            if features is None or not _looks_like_heading(features, body_size):
                continue

            block["type"] = "heading"
            level = _numbering_level(text)
            promoted.append((block, features.median_size, level))

    if promoted:
        level_by_size = _size_levels([size for _, size, _ in promoted])
        for block, size, numbered_level in promoted:
            block["heading_level"] = numbered_level or level_by_size.get(
                round(size, 1), 1
            )
        logger.info("Promoted %d typography-derived headings", len(promoted))
    return raw


def extract_pdf_typography(pdf_bytes: bytes) -> TypographyPages:
    """Read character-level font metadata; heavy import stays inside this path."""
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LAParams, LTChar

    pages: TypographyPages = {}
    stream = io.BytesIO(pdf_bytes)
    for page_index, page_layout in enumerate(
        extract_pages(stream, laparams=LAParams()), start=1
    ):
        spans: list[CharSpan] = []

        def walk(element) -> None:
            if isinstance(element, LTChar):
                spans.append(
                    CharSpan(
                        text=element.get_text(),
                        fontname=str(getattr(element, "fontname", "")),
                        size=float(getattr(element, "size", 0.0) or 0.0),
                        x0=float(element.bbox[0]),
                        y0=float(element.bbox[1]),
                        x1=float(element.bbox[2]),
                        y1=float(element.bbox[3]),
                    )
                )
                return
            for child in getattr(element, "_objs", []):
                walk(child)

        walk(page_layout)
        pages[page_index] = PageTypography(
            width=float(page_layout.width),
            height=float(page_layout.height),
            spans=spans,
        )
    return pages


def _body_font_size(pages: TypographyPages) -> float:
    weighted: list[float] = []
    for page in pages.values():
        for span in page.spans:
            if not span.text.strip() or span.size <= 0:
                continue
            weighted.extend([span.size] * max(1, len(span.text.strip())))
    return statistics.median(weighted) if weighted else 0.0


def _can_promote(block: dict) -> bool:
    raw_type = str(block.get("type", "")).strip().lower()
    return raw_type not in _NON_HEADING_TYPES


def _heading_length_ok(text: str) -> bool:
    if not text:
        return False
    words = len(text.split())
    if words <= 12:
        return True
    cjk_chars = len(_CJK_PATTERN.findall(text))
    return cjk_chars >= max(2, int(len(text) * 0.5)) and len(text) <= 40


def _numbering_level(text: str) -> int | None:
    normalized = text.strip()
    if _ROMAN_HEADING.match(normalized):
        return 1
    if _LETTER_HEADING.match(normalized):
        return 2
    if _PAREN_DIGIT_HEADING.match(normalized):
        return 3
    if _PAREN_LETTER_HEADING.match(normalized):
        return 4
    match = NUMBERED_HEADING_PATTERN.match(normalized)
    if not match:
        return None
    return len(match.group("number").split("."))


def _block_bbox_normalized(
    block: dict,
    page: PageTypography,
    bbox_unit: str,
) -> tuple[float, float, float, float] | None:
    raw_bbox = block.get("bbox")
    if isinstance(raw_bbox, dict):
        values = (
            raw_bbox.get("x0"),
            raw_bbox.get("y0"),
            raw_bbox.get("x1"),
            raw_bbox.get("y1"),
        )
    elif isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        values = tuple(raw_bbox[:4])
    else:
        return None
    try:
        x0, y0, x1, y1 = (float(value) for value in values)
    except (TypeError, ValueError):
        return None

    if bbox_unit == "normalized_1000":
        x0, y0, x1, y1 = x0 / 1000.0, y0 / 1000.0, x1 / 1000.0, y1 / 1000.0
    elif bbox_unit != "normalized_1":
        if page.width <= 0 or page.height <= 0:
            return None
        x0, x1 = x0 / page.width, x1 / page.width
        # pypdf boxes use PDF's bottom-left origin; the rest of the pipeline
        # (and MinerU) uses top-left origin, so flip here.
        y0, y1 = 1.0 - y1 / page.height, 1.0 - y0 / page.height

    return (
        max(0.0, min(1.0, x0)),
        max(0.0, min(1.0, y0)),
        max(0.0, min(1.0, x1)),
        max(0.0, min(1.0, y1)),
    )


def _is_margin_box(bbox: tuple[float, float, float, float]) -> bool:
    _, y0, _, y1 = bbox
    return y1 <= 0.1 or y0 >= 0.9


@dataclass(frozen=True)
class _BlockTypography:
    char_count: int
    bold_ratio: float
    median_size: float


def _collect_features(
    spans: list[CharSpan],
    bbox: tuple[float, float, float, float],
    page_width: float = 0.0,
    page_height: float = 0.0,
) -> _BlockTypography | None:
    x0, y0, x1, y1 = bbox
    chars = 0
    bold_chars = 0
    weighted_sizes: list[float] = []
    for span in spans:
        text = span.text.strip()
        if not text:
            continue
        # Span boxes are PDF points; callers pass normalized block boxes, so
        # matching happens in point space when page dimensions are available.
        if page_width > 0 and page_height > 0:
            sx0, sx1 = span.x0 / page_width, span.x1 / page_width
            sy0, sy1 = span.y0 / page_height, span.y1 / page_height
        else:
            continue
        center_x = (sx0 + sx1) / 2
        # Span y is bottom-left origin; block bboxes are top-left origin.
        center_y = 1.0 - ((sy0 + sy1) / 2)
        if not (x0 <= center_x <= x1 and y0 <= center_y <= y1):
            continue
        count = len(text)
        chars += count
        if _BOLD_FONT_PATTERN.search(span.fontname):
            bold_chars += count
        weighted_sizes.extend([span.size] * count)
    if chars == 0 or not weighted_sizes:
        return None
    return _BlockTypography(
        char_count=chars,
        bold_ratio=bold_chars / chars,
        median_size=statistics.median(weighted_sizes),
    )


def _looks_like_heading(features: _BlockTypography, body_size: float) -> bool:
    if body_size <= 0:
        return False
    size_ratio = features.median_size / body_size
    bold_heading = features.bold_ratio >= 0.8 and size_ratio >= 1.0
    large_heading = size_ratio >= 1.15 and features.bold_ratio >= 0.2
    return bold_heading or large_heading


def _size_levels(sizes: list[float]) -> dict[float, int]:
    distinct = sorted({round(size, 1) for size in sizes}, reverse=True)
    return {size: min(index + 1, 6) for index, size in enumerate(distinct)}
