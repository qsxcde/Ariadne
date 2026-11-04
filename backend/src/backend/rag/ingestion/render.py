"""Single source of truth for turning DocumentIR blocks into text.

Both chunk text and exported Markdown go through :func:`render_block`, so the
indexed content and the preview can never drift apart.
"""

from backend.rag.ingestion.document_ir import BlockIR, DocumentIR

# MinerU 行间公式可能自带 `$$`、`\[ \]`、`\( \)` 包裹；索引与渲染只保留 LaTeX 本体。
_FORMULA_DELIMITER_PAIRS: tuple[tuple[str, str], ...] = (
    ("$$", "$$"),
    ("\\[", "\\]"),
    ("\\(", "\\)"),
)


def clean_formula(text: str) -> str:
    """Strip formula delimiters so callers get bare LaTeX."""
    cleaned = text.strip()
    for left, right in _FORMULA_DELIMITER_PAIRS:
        if cleaned.startswith(left) and cleaned.endswith(right):
            body = cleaned[len(left) : len(cleaned) - len(right)].strip()
            if body:
                return body
    return cleaned


def ordered_blocks(document: DocumentIR) -> list[BlockIR]:
    """Return blocks in deterministic reading order."""
    blocks = document.blocks or [block for page in document.pages for block in page.blocks]
    return sorted(blocks, key=lambda block: (block.page_number, block.reading_order, block.block_index))


def render_block(block: BlockIR) -> str:
    """Render one block as plain text or Markdown."""
    text = block.text.strip()
    if block.type == "title":
        return f"# {text}" if text else ""
    if block.type == "heading":
        return f"## {text}" if text else ""
    if block.type == "table":
        return f"[Table on page {block.page_number}]\n{text}" if text else f"[Table on page {block.page_number}]"
    if block.type == "figure":
        return ""
    if block.type == "figure_caption":
        return f"**Figure:** {text}" if text else ""
    if block.type == "table_caption":
        return f"**Table:** {text}" if text else ""
    if block.type == "reference":
        return text
    if block.type == "formula":
        if text:
            return clean_formula(text)
        section = " > ".join(block.section_path) if block.section_path else "Document"
        return f"[Formula on page {block.page_number} near {section}]"
    return text
