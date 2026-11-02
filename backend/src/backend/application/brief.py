"""Generate a citation-bearing 5-minute brief for one paper."""

import json
import logging
import time
from typing import Any

from backend import composition
from backend.application.papers import get_accessible_paper
from backend.domain.models import Chunk
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.sessions import now_iso

logger = logging.getLogger(__name__)

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


def _document_signature(documents: list[dict[str, Any]]) -> str:
    return ",".join(
        f"{document['id']}:{document.get('updated_at', '')}:{document.get('status', '')}"
        for document in documents
    )


def _load_cached_brief(paper: dict[str, Any], signature: str) -> dict[str, Any] | None:
    raw = paper.get("metadata_json")
    if not raw:
        return None
    try:
        metadata = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(metadata, dict):
        return None
    cache = metadata.get("brief_cache")
    if not isinstance(cache, dict) or cache.get("signature") != signature:
        return None
    payload = cache.get("payload")
    if not isinstance(payload, dict):
        return None
    return {
        "paper_id": paper["id"],
        "generated_at": str(cache.get("generated_at") or now_iso()),
        **payload,
    }


def _store_cached_brief(
    paper: dict[str, Any], signature: str, brief: dict[str, Any]
) -> None:
    raw = paper.get("metadata_json")
    try:
        metadata = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["brief_cache"] = {
        "signature": signature,
        "generated_at": brief["generated_at"],
        "payload": {
            key: value
            for key, value in brief.items()
            if key not in {"paper_id", "generated_at"}
        },
    }
    try:
        paper_repo.update_metadata_json(
            paper["id"], json.dumps(metadata, ensure_ascii=False)
        )
    except Exception:  # 缓存失败不影响主流程
        logger.warning("brief cache write failed for %s", paper["id"], exc_info=True)


def _log_generation(paper_id: str, elapsed_ms: float) -> None:
    from backend.adapters.llm.llm import last_usage

    usage = last_usage() or {}
    logger.info(
        "llm_generation operation=brief paper_id=%s elapsed_ms=%.1f prompt_tokens=%s completion_tokens=%s",
        paper_id,
        elapsed_ms,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )


def generate_paper_brief(
    paper_id: str,
    user_id: str | None,
    *,
    completer: Any | None = None,
    force: bool = False,
) -> dict[str, Any]:
    paper = get_accessible_paper(paper_id, user_id)
    documents = document_repo.list_documents_for_paper(paper_id)
    if not documents:
        raise ValueError("Paper has no document yet")
    signature = _document_signature([dict(document) for document in documents])
    if not force:
        cached = _load_cached_brief(dict(paper), signature)
        if cached is not None:
            logger.info("brief_cache_hit paper_id=%s", paper_id)
            return cached
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
    started = time.perf_counter()
    raw = runner.complete(_BRIEF_PROMPT.replace("{sections}", digest))
    _log_generation(paper_id, (time.perf_counter() - started) * 1000)
    brief = _parse_brief(raw, sections)
    result = {
        "paper_id": paper["id"],
        "generated_at": now_iso(),
        **brief,
    }
    _store_cached_brief(dict(paper), signature, result)
    return result
