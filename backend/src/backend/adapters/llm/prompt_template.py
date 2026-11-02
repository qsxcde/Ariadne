from backend.domain.models import Chunk
from backend.prompts.loader import load_prompt

SYSTEM_PROMPT = load_prompt("rag_answer")

_HISTORY_MAX_MESSAGES = 6
_HISTORY_MAX_CHARS = 1200


def build_prompt(
    chunks: list[Chunk],
    question: str,
    history: list[dict] | None = None,
) -> str:
    context = "\n\n---\n\n".join(_format_chunk_for_prompt(chunk) for chunk in chunks)
    parts = [SYSTEM_PROMPT]
    history_block = _format_history(history, question)
    if history_block:
        parts.append(history_block)
    parts.append(f"论文片段:\n{context}")
    parts.append(f"用户问题: {question}")
    parts.append("请用中文作答。")
    return "\n\n".join(parts)


def _format_history(history: list[dict] | None, question: str) -> str:
    if not history:
        return ""
    current = question.strip()
    lines: list[str] = []
    for message in history[-_HISTORY_MAX_MESSAGES:]:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if role == "user" and content == current:
            continue
        label = "用户" if role == "user" else "助手"
        lines.append(f"{label}: {content[:500]}")
    if not lines:
        return ""
    text = "\n".join(lines)
    if len(text) > _HISTORY_MAX_CHARS:
        text = text[-_HISTORY_MAX_CHARS:]
    return "对话历史（仅用于理解指代，不要复述）：\n" + text


def _format_chunk_header(chunk: Chunk) -> str:
    if chunk.metadata.section_path:
        section = " > ".join(s for s in chunk.metadata.section_path if s)
    elif chunk.metadata.section:
        section = chunk.metadata.section
    else:
        section = "Document"
    parts = [f"Section: {section}"]
    page_label = _format_page_range(chunk)
    if page_label:
        parts.append(f"Page: {page_label}")
    parts.append(f"Chunk: {chunk.metadata.chunk_index}")
    if chunk.metadata.confidence is not None and chunk.metadata.confidence < 0.5:
        parts.append("Low confidence source")
    return f"[{' | '.join(parts)}]"


def _format_chunk_for_prompt(chunk: Chunk) -> str:
    return f"{_format_chunk_header(chunk)}\n{chunk.text}"


def _format_page_range(chunk: Chunk) -> str | None:
    start = chunk.metadata.page_start
    end = chunk.metadata.page_end
    if start is None and end is None:
        return None
    if start is None:
        return str(end)
    if end is None or end == start:
        return str(start)
    return f"{start}-{end}"
