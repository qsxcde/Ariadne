"""Generate a citation-bearing 5-minute brief for one paper."""

import json
from typing import Any

from backend import composition
from backend.application.papers import get_accessible_paper
from backend.domain.models import Chunk
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.sessions import now_iso

_MAX_SECTIONS = 8
_SECTION_CHAR_BUDGET = 1600

_BRIEF_PROMPT = """你是一个论文速读助手。下面是按章节整理的论文片段。
只输出一个 JSON 对象，不要输出数组、Markdown 代码块或解释。

严格按这个示例的字段和类型输出：
{"tldr": "一句话总结", "contributions": ["贡献1 [Section: Method | Chunk: 0]"], "method": "方法概述 [Section: Method | Chunk: 0]", "experiments": "实验概述", "limitations": "局限", "takeaways": ["要点1"], "sections": [{"title": "Method", "summary": "本节摘要", "chunk_indexes": [0]}]}

要求：
1. 每个关键结论都带引用，格式为 [Section: 章节标题 | Chunk: 序号]。
2. 没有依据的内容写“未提及”，不要编造。
3. 保持中文、简洁。

论文片段：
{sections}
"""


def _section_title(chunk: Chunk) -> str:
    if chunk.metadata.section_path:
        return " > ".join(chunk.metadata.section_path)
    return chunk.metadata.section or "Document"


def _build_section_digest(chunks: list[Chunk]) -> str:
    grouped: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        grouped.setdefault(_section_title(chunk), []).append(chunk)

    lines: list[str] = []
    for title, section_chunks in list(grouped.items())[:_MAX_SECTIONS]:
        section_chunks.sort(key=lambda item: item.metadata.chunk_index)
        lines.append(f"## {title}")
        used = 0
        for chunk in section_chunks:
            text = chunk.text.strip()
            if not text:
                continue
            if used >= _SECTION_CHAR_BUDGET:
                break
            remaining = _SECTION_CHAR_BUDGET - used
            excerpt = text[:remaining]
            used += len(excerpt)
            lines.append(
                f"[Section: {title} | Chunk: {chunk.metadata.chunk_index}] {excerpt}"
            )
    return "\n\n".join(lines)


def _parse_brief(raw: str, sections: list[dict[str, Any]]) -> dict[str, Any]:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = {"tldr": raw.strip()}

    def as_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    parsed_sections = payload.get("sections")
    normalized_sections = sections
    if isinstance(parsed_sections, list):
        normalized_sections = [
            {
                "title": str(item.get("title") or ""),
                "summary": str(item.get("summary") or ""),
                "chunk_indexes": [
                    int(index)
                    for index in item.get("chunk_indexes", [])
                    if isinstance(index, int)
                ],
            }
            for item in parsed_sections
            if isinstance(item, dict)
        ] or sections

    return {
        "tldr": str(payload.get("tldr") or "未提及"),
        "contributions": as_list(payload.get("contributions")),
        "method": str(payload.get("method") or "未提及"),
        "experiments": str(payload.get("experiments") or "未提及"),
        "limitations": str(payload.get("limitations") or "未提及"),
        "takeaways": as_list(payload.get("takeaways")),
        "sections": normalized_sections,
    }


def generate_paper_brief(
    paper_id: str,
    user_id: str | None,
    *,
    completer: Any | None = None,
) -> dict[str, Any]:
    paper = get_accessible_paper(paper_id, user_id)
    documents = document_repo.list_documents_for_paper(paper_id)
    if not documents:
        raise ValueError("Paper has no document yet")
    sessions = session_repo.list_sessions_for_paper(paper_id)
    if not sessions:
        raise ValueError("Paper has no reading session yet")

    session_id = sessions[0]["id"]
    document_ids = [document["id"] for document in documents]
    chunks = chunk_repo.list_chunks_for_documents(session_id, document_ids)
    if not chunks:
        raise ValueError("Paper is not indexed yet")

    digest = _build_section_digest(chunks)
    section_stub: list[dict[str, Any]] = [
        {
            "title": _section_title(chunk),
            "summary": "",
            "chunk_indexes": [chunk.metadata.chunk_index],
        }
        for chunk in chunks[:_MAX_SECTIONS]
    ]
    seen: set[str] = set()
    sections: list[dict[str, Any]] = []
    for item in section_stub:
        title = str(item["title"])
        if title in seen:
            continue
        seen.add(title)
        sections.append(item)

    runner = completer or composition.text_completer()
    raw = runner.complete(_BRIEF_PROMPT.replace("{sections}", digest))
    brief = _parse_brief(raw, sections)
    return {
        "paper_id": paper["id"],
        "generated_at": now_iso(),
        **brief,
    }
