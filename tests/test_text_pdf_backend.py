"""Text PDF fallback backend."""

from io import BytesIO

import pytest
from pypdf import PdfWriter

from backend.rag.ingestion.text_pdf_backend import TextPDFBackend


@pytest.mark.unit
def test_text_backend_parses_a_real_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)

    result = TextPDFBackend().parse(buffer.getvalue(), "blank.pdf")

    assert result.page_count == 1
    assert result.source_parser == "pypdf-text"


@pytest.mark.unit
def test_text_backend_rejects_garbage():
    with pytest.raises(RuntimeError, match="cannot be parsed"):
        TextPDFBackend().parse(b"not a pdf", "bad.pdf")
