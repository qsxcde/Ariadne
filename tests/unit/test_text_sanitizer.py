"""Broken math-font glyphs are repaired without rewriting Chinese prose."""

import pytest

from backend.rag.ingestion.text_sanitizer import (
    cjk_ratio,
    sanitize_extracted_text,
    wrap_bare_latex,
)


@pytest.mark.unit
def test_drops_isolated_cjk_glyph_inside_formula_paragraph():
    text = "HM 2 ∗ αB = 2 φ ′a 覂 XG3X − G4φ + 8H Ẋ 覂 G4X"

    cleaned = sanitize_extracted_text(text)

    assert "覂" not in cleaned
    assert "∗" not in cleaned and "−" not in cleaned
    assert "XG3X" in cleaned and "G4X" in cleaned


@pytest.mark.unit
def test_keeps_chinese_paragraph_untouched():
    text = "这是一个 覂 测试：准确率 = 95%，模型 = 很好。"

    assert cjk_ratio(text) > 0.3
    assert sanitize_extracted_text(text) == text


@pytest.mark.unit
def test_normalises_math_codepoints_even_without_garbage():
    assert sanitize_extracted_text("a ∗ b − c") == "a * b - c"


@pytest.mark.unit
def test_ignores_plain_prose_with_spaced_cjk():
    # 没有足够的数学标记时不做孤立 CJK 删除
    assert sanitize_extracted_text("第 1 节 覂 结论") == "第 1 节 覂 结论"


@pytest.mark.unit
def test_empty_text_is_returned_as_is():
    assert sanitize_extracted_text("") == ""


@pytest.mark.unit
def test_wraps_bare_inline_latex():
    text = (
        "Let \\mathbf { \\boldsymbol { \\mathsf { \\mathbf { \\theta } } } } "
        "denote the learnable gate-logit vector."
    )

    cleaned = wrap_bare_latex(text)

    assert cleaned.startswith("Let $\\mathbf")
    assert cleaned.endswith("$ denote the learnable gate-logit vector.")


@pytest.mark.unit
def test_wrap_bare_latex_is_idempotent():
    text = "能量满足 $E = mc^2$ 且 $\\alpha_1$ 不变"

    assert wrap_bare_latex(text) == text


@pytest.mark.unit
def test_wraps_subscript_only_latex():
    assert wrap_bare_latex("where \\alpha_1 is fixed") == "where $\\alpha_1$ is fixed"


@pytest.mark.unit
def test_does_not_wrap_paths_or_plain_prose():
    assert wrap_bare_latex("C:\\Users\\name") == "C:\\Users\\name"
    assert wrap_bare_latex("A number of N-body frameworks") == "A number of N-body frameworks"
