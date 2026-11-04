"""Generate a small glossary from a paper's chunks."""

from typing import Any

from backend.application.library.papers import get_accessible_paper
from backend.domain.models import Chunk
from backend.domain.ports import TextCompleter
from backend.rag.llm_output import parse_json_object
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.sessions import now_iso

_PROMPT = """你是论文阅读助手。请从下面的论文片段中提取 5-10 个关键术语/概念。
只输出 JSON，不要 Markdown 代码块：
{
  "terms": [
    {"term": "术语", "definition": "一句话解释", "section": "章节", "chunk_index": 0}
  ]
}
要求：定义只依据片段；不确定的不要编造。

片段：
{digest}
"""


def _digest(chunks: list[Chunk]) -> str:
    # 推理模型对长上下文会持续思考；摘要控制在约 3.6k 字符，保证正文预算。
    return "\n\n".join(
        f"[Section: {chunk.metadata.section} | Chunk: {chunk.metadata.chunk_index}] {chunk.text[:600]}"
        for chunk in chunks[:6]
    )


def _parse(raw: str) -> list[dict[str, Any]]:
    try:
        payload = parse_json_object(raw)
    except (TypeError, ValueError):
        return []
    terms = payload.get("terms")
    if not isinstance(terms, list):
        return []
    return [
        {
            "term": str(item.get("term") or ""),
            "definition": str(item.get("definition") or ""),
            "section": str(item.get("section") or ""),
            "chunk_index": int(item.get("chunk_index") or 0),
        }
        for item in terms
        if isinstance(item, dict) and str(item.get("term") or "").strip()
    ]


def generate_glossary(
    paper_id: str,
    user_id: str | None,
    *,
    completer: TextCompleter,
) -> dict[str, Any]:
    paper = get_accessible_paper(paper_id, user_id)
    sessions = session_repo.list_sessions_for_paper(paper_id)
    documents = document_repo.list_documents_for_paper(paper_id)
    if not sessions or not documents:
        raise ValueError("Paper is not indexed yet")
    chunks = chunk_repo.list_chunks_for_documents(
        sessions[0]["id"], [document["id"] for document in documents]
    )
    if not chunks:
        raise ValueError("Paper is not indexed yet")
    from backend.application.reading.generation_log import generation_timer

    runner = completer
    with generation_timer("glossary", paper_id=paper_id):
        raw = runner.complete(_PROMPT.replace("{digest}", _digest(chunks)))
    terms = _parse(raw)
    if not terms:
        raise ValueError("模型未返回可解析的术语，请重试")
    return {
        "paper_id": paper["id"],
        "terms": terms,
        "generated_at": now_iso(),
    }
