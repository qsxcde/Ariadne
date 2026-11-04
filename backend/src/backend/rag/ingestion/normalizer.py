import logging
from typing import cast

from backend.domain.models import BBoxUnit
from backend.rag.ingestion.document_ir import BBox, BlockIR, BlockType, DocumentIR, PageIR
from backend.rag.ingestion.document_ir import BlockLink
from backend.rag.ingestion.block_classifier import clean_heading, confidence_for_type, detect_block_type
from backend.rag.ingestion.linker import attach_caption_links
from backend.domain.parsing import ParserBackend, RawParserResult
from backend.rag.ingestion.quality_reporter import build_quality_report, find_repeated_header_footer_texts
from backend.rag.ingestion.reading_order import bbox_tuple, sorted_blocks_for_reading_order
from backend.rag.ingestion.text_sanitizer import sanitize_extracted_text, wrap_bare_latex

logger = logging.getLogger(__name__)
from backend.rag.ingestion.section_builder import (
    HEADING_BLOCK_TYPES,
    next_section_path,
    outline_from_blocks,
)


def normalize_parser_output(
    raw: RawParserResult,
    paper_id: str,
    filename: str,
    parser_backend: ParserBackend,
) -> DocumentIR:
    """Normalize parser-specific output into the stable DocumentIR contract."""
    pages: list[PageIR] = []
    all_blocks: list[BlockIR] = []
    current_section: list[str] = ["Abstract"]
    in_references = False
    reading_order = 0
    canonical_pages, bbox_unit = _canonicalize_pages(raw.pages, raw.bbox_unit)
    repeated_header_footer_texts = find_repeated_header_footer_texts(
        canonical_pages, _bbox_model
    )

    for page_data in canonical_pages:
        page_number = int(page_data.get("page_number", len(pages) + 1))
        page_width = float(page_data.get("width", 0.0))
        page_height = float(page_data.get("height", 0.0))
        page_blocks: list[BlockIR] = []
        raw_blocks = page_data.get("blocks", [])
        for index, block_data in enumerate(raw_blocks):
            block_data["_original_index"] = index
        sorted_blocks = sorted_blocks_for_reading_order(raw_blocks, page_width, _bbox_model)
        for block_data in sorted_blocks:
            text = sanitize_extracted_text(str(block_data.get("text", "")).strip())
            if not text and str(block_data.get("type", "")).strip().lower() not in {"formula", "figure"}:
                continue
            bbox = _bbox_model(block_data.get("bbox"))
            if not text and bbox.x0 == 0.0 and bbox.x1 == 0.0 and bbox.y0 == 0.0 and bbox.y1 == 0.0:
                logger.warning(
                    "Empty block at p%d with zero bbox, type=%s; skipping",
                    page_number, block_data.get("type"),
                )
                continue
            block_type = _resolve_block_type(
                block_data=block_data,
                text=text,
                bbox=bbox,
                page_height=page_height,
                repeated_header_footer_texts=repeated_header_footer_texts,
                in_references=in_references,
            )
            if block_type == "unknown" and not text:
                continue
            if _is_visual_only_block(block_data, block_type):
                continue
            if block_type != "formula":
                # 行内公式丢了 $ 分隔符时补回来，否则前端只能显示反斜杠
                text = wrap_bare_latex(text)
            heading_level: int | None = None
            if block_type in HEADING_BLOCK_TYPES:
                heading_level = _resolve_heading_level(block_data)
                current_section = next_section_path(
                    current_section, text, level=heading_level
                )
                cleaned_text = clean_heading(text)
                heading_lower = cleaned_text.lower()
                if heading_lower == "references":
                    in_references = True
                elif in_references and _is_post_reference_heading(heading_lower):
                    in_references = False
            elif block_type == "reference":
                current_section = ["References"]
                in_references = True
                cleaned_text = text
            elif block_type == "header_footer":
                cleaned_text = text
            else:
                cleaned_text = text
            block = BlockIR(
                id=f"p{page_number}-ro{reading_order}",
                page_number=page_number,
                block_index=int(block_data.pop("_original_index", reading_order)),
                type=block_type,
                text=cleaned_text,
                bbox=bbox,
                reading_order=reading_order,
                section_path=current_section.copy() if block_type != "header_footer" else [],
                heading_level=heading_level,
                confidence=_resolve_confidence(block_data, block_type, cleaned_text),
                has_image=bool(block_data.get("has_image")),
                links=_resolve_links(block_data),
            )
            reading_order += 1
            page_blocks.append(block)
            all_blocks.append(block)
        attach_caption_links(page_blocks)
        pages.append(
            PageIR(
                page_number=page_number,
                width=page_width,
                height=float(page_data.get("height", 0.0)),
                rotation=int(page_data.get("rotation", 0)),
                blocks=page_blocks,
            )
        )

    fallback_reason = raw.metadata.get("fallback_reason")
    quality_report = build_quality_report(
        parser_backend=parser_backend,
        page_count=raw.page_count,
        blocks=all_blocks,
        parser_warnings=raw.warnings,
        fallback_reason=str(fallback_reason) if fallback_reason else None,
    )
    return DocumentIR(
        document_id=paper_id,
        filename=filename,
        page_count=raw.page_count,
        parser_name=parser_backend.name,
        parser_version=parser_backend.version,
        pages=pages,
        blocks=all_blocks,
        outline=outline_from_blocks(all_blocks),
        quality_report=quality_report,
        bbox_unit=bbox_unit,
    )


def _canonicalize_pages(
    pages: list[dict],
    bbox_unit: BBoxUnit,
) -> tuple[list[dict], BBoxUnit]:
    """Put every parser output on one coordinate system before normalization.

    Cloud ``content_list`` bboxes are 0-1000 normalized, while pypdf reports
    PDF points. Reading-order and margin heuristics need consistent page units,
    so normalized inputs are converted to 0-1 together with page dimensions.
    """
    if bbox_unit == "points":
        return pages, "points"

    scale = 1000.0 if bbox_unit == "normalized_1000" else 1.0
    canonical: list[dict] = []
    for page in pages:
        page_copy = dict(page)
        page_copy["width"] = 1.0
        page_copy["height"] = 1.0
        blocks: list[dict] = []
        for block in page.get("blocks", []) or []:
            block_copy = dict(block)
            bbox = block.get("bbox")
            if isinstance(bbox, dict):
                block_copy["bbox"] = {
                    key: _scale_bbox_value(value, scale) for key, value in bbox.items()
                }
            elif isinstance(bbox, (list, tuple)):
                block_copy["bbox"] = [
                    _scale_bbox_value(value, scale) for value in bbox[:4]
                ]
            blocks.append(block_copy)
        page_copy["blocks"] = blocks
        canonical.append(page_copy)
    return canonical, "normalized_1"


def _scale_bbox_value(value: object, scale: float) -> float:
    try:
        return float(value) / scale
    except (TypeError, ValueError):
        return 0.0


def _bbox_model(value: object) -> BBox:
    x0, y0, x1, y1 = bbox_tuple(value)
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


def _resolve_block_type(
    block_data: dict,
    text: str,
    bbox: BBox,
    page_height: float,
    repeated_header_footer_texts: set[str],
    in_references: bool,
) -> BlockType:
    raw_type = str(block_data.get("type", "")).strip().lower()
    if raw_type in {
        "title",
        "heading",
        "paragraph",
        "table",
        "figure",
        "figure_caption",
        "table_caption",
        "formula",
        "footnote",
        "reference",
        "header_footer",
        "unknown",
    }:
        return cast(BlockType, raw_type)
    return detect_block_type(
        text=text,
        bbox=bbox,
        page_height=page_height,
        repeated_header_footer_texts=repeated_header_footer_texts,
        in_references=in_references,
    )


def _resolve_heading_level(block_data: dict) -> int | None:
    """Read the parser-reported heading depth; ``None`` falls back to numbering."""
    for key in ("heading_level", "level", "text_level"):
        raw = block_data.get(key)
        if raw is None:
            continue
        try:
            level = int(raw)
        except (TypeError, ValueError):
            continue
        if level >= 1:
            return level
    return None


def _resolve_confidence(block_data: dict, block_type: BlockType, text: str) -> float:
    raw_confidence = block_data.get("confidence")
    if raw_confidence is not None:
        try:
            return float(raw_confidence)
        except (TypeError, ValueError):
            pass
    return confidence_for_type(block_type, text)


def _resolve_links(block_data: dict) -> list[BlockLink]:
    links: list[BlockLink] = []
    for item in block_data.get("links", []) or []:
        if not isinstance(item, dict):
            continue
        target_block_id = str(item.get("target_block_id", "")).strip()
        relation = str(item.get("relation", "")).strip()
        if not target_block_id or not relation:
            continue
        links.append(BlockLink(target_block_id=target_block_id, relation=relation))
    return links


def _is_visual_only_block(block_data: dict, block_type: str) -> bool:
    raw_type = str(block_data.get("type", "")).strip().lower()
    return raw_type in {"image", "figure", "picture"} and block_type not in {
        "figure",
        "figure_caption",
        "table_caption",
    }


def _is_post_reference_heading(heading_lower: str) -> bool:
    return heading_lower in {
        "appendix", "appendices", "supplementary", "supplementary material",
        "acknowledgments", "acknowledgements",
    } or heading_lower.startswith("appendix") or heading_lower.startswith("supplementary")
