from backend.rag.ingestion.document_ir import BlockIR
from backend.rag.ingestion.block_classifier import NUMBERED_HEADING_PATTERN, clean_heading

# MinerU 把标题标成 ``title``，启发式识别出的叫 ``heading``；两者都参与章节层级。
HEADING_BLOCK_TYPES = frozenset({"title", "heading"})


def next_section_path(
    current_section: list[str],
    text: str,
    level: int | None = None,
) -> list[str]:
    """Return the section path for a heading block.

    ``level`` is the parser-reported heading depth (1-based). It wins over the
    numbering heuristic: MinerU titles like ``I. INTRODUCTION`` (Roman numerals)
    or fully unnumbered headings cannot be resolved by ``NUMBERED_HEADING_PATTERN``.
    """
    cleaned = clean_heading(text)
    if level is not None:
        return _path_for_level(current_section, cleaned, level)

    match = NUMBERED_HEADING_PATTERN.match(text.strip())
    if not match:
        if len(current_section) > 1:
            return current_section[:-1] + [cleaned]
        return [cleaned]
    return _path_for_level(current_section, cleaned, len(match.group("number").split(".")))


def _path_for_level(current_section: list[str], cleaned: str, level: int) -> list[str]:
    if level <= 1:
        return [cleaned]
    parent = current_section[: level - 1]
    if len(parent) < level - 1:
        parent = parent + ["Unknown"] * ((level - 1) - len(parent))
    return parent + [cleaned]


def outline_from_blocks(blocks: list[BlockIR]) -> list[str]:
    return [block.text for block in blocks if block.type in HEADING_BLOCK_TYPES]
