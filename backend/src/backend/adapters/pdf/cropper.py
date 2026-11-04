"""Render normalized block boxes from the original PDF as PNG crops."""

from __future__ import annotations

import io
import math
from pathlib import Path

import pypdfium2 as pdfium

MAX_CROP_SCALE = 3.0
MAX_CROP_PIXELS = 4_000_000
# MinerU boxes hug the glyphs; a little padding keeps descenders/italic tails.
CROP_PADDING_POINTS = 2.0


class CropRenderError(RuntimeError):
    """Raised when a block box cannot be rendered from the source PDF."""


def render_block_crop(
    pdf_path: Path,
    page_number: int,
    bbox: dict[str, float],
    *,
    scale: float = 2.0,
) -> bytes:
    """Render a 0-1 normalized box (top-left origin) to PNG bytes."""
    scale = max(1.0, min(MAX_CROP_SCALE, float(scale)))
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:  # pdfium raises its own error type
        raise CropRenderError(f"Cannot open PDF for cropping: {exc}") from exc

    try:
        if page_number < 1 or page_number > len(pdf):
            raise CropRenderError(
                f"Page {page_number} is outside the PDF (1-{len(pdf)})"
            )
        page = pdf[page_number - 1]
        width, height = page.get_size()
        if width <= 0 or height <= 0:
            raise CropRenderError("PDF page has no renderable size")

        x0 = _clamp(bbox.get("x0", 0.0)) * width
        y0 = _clamp(bbox.get("y0", 0.0)) * height
        x1 = _clamp(bbox.get("x1", 0.0)) * width
        y1 = _clamp(bbox.get("y1", 0.0)) * height
        if abs(x1 - x0) < 1.0 or abs(y1 - y0) < 1.0:
            raise CropRenderError("Block box is too small to render")
        left = max(0.0, min(x0, x1) - CROP_PADDING_POINTS)
        right = min(width, max(x0, x1) + CROP_PADDING_POINTS)
        top = max(0.0, min(y0, y1) - CROP_PADDING_POINTS)
        bottom = min(height, max(y0, y1) + CROP_PADDING_POINTS)
        if right - left < 1.0 or bottom - top < 1.0:
            raise CropRenderError("Block box is too small to render")

        # pypdfium2's crop is a margin tuple measured from each page edge.
        crop = (left, height - bottom, width - right, top)
        scale = _limit_scale(scale, right - left, bottom - top)
        bitmap = page.render(scale=scale, crop=crop)
        pil_image = bitmap.to_pil()
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG", optimize=True)
        return buffer.getvalue()
    except CropRenderError:
        raise
    except Exception as exc:
        raise CropRenderError(f"Failed to render block crop: {exc}") from exc
    finally:
        pdf.close()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _limit_scale(scale: float, width_points: float, height_points: float) -> float:
    """Keep pathological boxes from allocating huge bitmaps."""
    pixels = width_points * height_points * scale * scale
    if pixels <= MAX_CROP_PIXELS:
        return scale
    return max(1.0, math.sqrt(MAX_CROP_PIXELS / (width_points * height_points)))
