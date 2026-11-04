"""Text PDF fallback backend."""

from io import BytesIO

import pytest
from pypdf import PdfWriter

from backend.adapters.parsers.text_pdf_backend import (
    TextPDFBackend,
    _blocks_for_page_text,
    _repeated_header_lines,
)


def _blocks(text: str, **kwargs) -> list[dict]:
    return _blocks_for_page_text(
        text=text,
        page_number=1,
        width=600.0,
        height=800.0,
        **kwargs,
    )


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


@pytest.mark.unit
def test_heading_recovery_uses_numbering_and_keywords():
    text = "\n".join(
        [
            "Prepared for submission to JCAP",
            "Mercury (Hg): a relativisticN-body",
            "1 Introduction",
            "Numerical tools have become an essential component",
            "in the study of cosmological perturbations.",
            "2.1 Method",
            "We describe the method.",
            "4.1.2 Covariant-theory approach 19",
            "REFERENCES",
            "[1] A. Author, Title, 2020.",
        ]
    )

    titles = [(block["text"], block["heading_level"]) for block in _blocks(text) if block["type"] == "title"]

    assert titles == [
        ("1 Introduction", 1),
        ("2.1 Method", 2),
        ("REFERENCES", 1),
    ]


@pytest.mark.unit
def test_multiline_prose_is_not_mistaken_for_heading():
    text = "\n".join(
        [
            "Numerical tools have become an essential component",
            "in the study of cosmological perturbations and the",
            "interpretation of large-scale structure observations.",
        ]
    )

    assert [block["type"] for block in _blocks(text)] == ["paragraph"]


@pytest.mark.unit
def test_repeated_header_lines_and_page_numbers_are_dropped():
    pages = [
        "\n".join(["Running header", f"body paragraph number {index}.", f"- {index + 1} -"])
        for index in range(3)
    ]
    repeated = _repeated_header_lines(pages)

    blocks = _blocks(pages[0], drop_lines=repeated)

    texts = " ".join(block["text"] for block in blocks)
    assert "Running header" not in texts
    assert "- 1 -" not in texts
    assert "body paragraph number 0." in texts


@pytest.mark.unit
def test_body_is_split_into_budget_sized_blocks():
    text = " ".join(f"word{index}" for index in range(12)) + "."

    blocks = _blocks(text, max_words=5)

    assert [block["type"] for block in blocks] == ["paragraph", "paragraph", "paragraph"]
