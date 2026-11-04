"""PDF block cropping stays inside the requested box and fails safely."""

from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfWriter

from backend.adapters.pdf.cropper import CropRenderError, render_block_crop


def _blank_pdf(path, width: int = 200, height: int = 100) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=width, height=height)
    with path.open("wb") as handle:
        writer.write(handle)


@pytest.mark.unit
def test_crop_renders_only_the_requested_region(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    _blank_pdf(pdf_path)

    image_bytes = render_block_crop(
        pdf_path,
        1,
        {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.6},
        scale=2.0,
    )

    image = Image.open(BytesIO(image_bytes))
    assert image.format == "PNG"
    # 80x40 pt box + 2 pt padding on each side, rendered at 2x.
    assert abs(image.width - 168) <= 2
    assert abs(image.height - 88) <= 2


@pytest.mark.unit
def test_crop_rejects_degenerate_boxes(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    _blank_pdf(pdf_path)

    with pytest.raises(CropRenderError):
        render_block_crop(
            pdf_path,
            1,
            {"x0": 0.1, "y0": 0.2, "x1": 0.1, "y1": 0.2},
        )


@pytest.mark.unit
def test_crop_rejects_missing_page(tmp_path):
    pdf_path = tmp_path / "paper.pdf"
    _blank_pdf(pdf_path)

    with pytest.raises(CropRenderError):
        render_block_crop(
            pdf_path,
            3,
            {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.6},
        )
