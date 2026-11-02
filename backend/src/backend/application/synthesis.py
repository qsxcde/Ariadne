"""Collection-level Q&A and structured paper comparison."""

import json
from typing import Any

from backend import composition
from backend.adapters.llm.prompt_template import build_prompt
from backend.application.collections import get_accessible_collection
from backend.application.papers import get_accessible_paper
from backend.domain.models import Chunk
from backend.rag.answer import RetrievalOptions, retrieve_context
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo

_COMPARE_PROMPT = """你是论文对比助手。请只根据给定片段，为下面这篇论文抽取统一字段。
输出 JSON，不要 Markdown 代码块：
{{
  "method": "方法（带 [Section: 章节 | Chunk: 序号] 引用）",
  "datasets": "数据集（带引用）",
  "metrics": "指标与主要结果（带引用）",
  "limitations": "局限（带引用）"
}}
没有依据写“未提及”。

论文：{title}
片段：
{digest}
"""


class _StaticChunkStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def add_chunks(self, _chunks: list[Chunk]) -> None:
        return None

    def list_chunks(self) -> list[Chunk]:
        return self._chunks

    def search(self, _query: str, _k: int = 5) -> list[Chunk]:
        return []


def _collection_chunks_and_map(
    collection_id: str, user_id: str | None
) -> tuple[list[Chunk], dict[str, str]]:
    get_accessible_collection(collection_id, user_id)
    papers = collection_repo.list_collection_papers(collection_id)
    all_chunks: list[Chunk] = []
    document_to_paper: dict[str, str] = {}
    for paper in papers:
        sessions = session_repo.list_sessions_for_paper(paper["id"])
        if not sessions:
            continue
        documents = document_repo.list_documents_for_paper(paper["id"])
        for document in documents:
            document_to_paper[document["id"]] = paper["id"]
        all_chunks.extend(
            chunk_repo.list_chunks_for_documents(
                sessions[0]["id"], [document["id"] for document in documents]
            )
        )
    return all_chunks, document_to_paper


def answer_collection(
    collection_id: str,
    user_id: str | None,
    question: str,
    *,
    completer: Any | None = None,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("Question is empty")
    chunks, document_to_paper = _collection_chunks_and_map(collection_id, user_id)
    if not chunks:
        raise ValueError("Collection has no indexed paper")

    store = _StaticChunkStore(chunks)
    options = RetrievalOptions(
        strategy="bm25",
        bm25_top_k=8,
        seed_top_k=8,
        max_expanded_chunks=8,
        same_section_window=0,
        adjacent_window=0,
        include_linked_blocks=False,
        enable_reranker=False,
        history_rewrite_enabled=False,
        term_expand_enabled=False,
    )
    context_chunks, sources = retrieve_context(store, question, options=options)
    if not context_chunks:
        raise ValueError("No relevant chunks found in collection")
    from backend.application.generation_log import generation_timer

    runner = completer or composition.text_completer()
    with generation_timer("collection_ask", paper_id=collection_id):
        answer = str(runner.complete(build_prompt(context_chunks, question))).strip()
    return {
        "answer": answer,
        "sources": [source.model_dump() for source in sources],
        "paper_ids": sorted(
            {
                document_to_paper.get(chunk.metadata.paper_id, chunk.metadata.paper_id)
                for chunk in context_chunks
            }
        ),
        "chunk_count": len(context_chunks),
    }


def compare_papers(
    collection_id: str,
    user_id: str | None,
    paper_ids: list[str],
    *,
    completer: Any | None = None,
) -> list[dict[str, Any]]:
    get_accessible_collection(collection_id, user_id)
    if not paper_ids:
        raise ValueError("paper_ids is empty")
    from backend.application.generation_log import generation_timer

    runner = completer or composition.text_completer()
    results: list[dict[str, Any]] = []
    for paper_id in paper_ids:
        paper = get_accessible_paper(paper_id, user_id)
        sessions = session_repo.list_sessions_for_paper(paper_id)
        documents = document_repo.list_documents_for_paper(paper_id)
        if not sessions or not documents:
            raise ValueError(f"Paper is not indexed: {paper_id}")
        chunks = chunk_repo.list_chunks_for_documents(
            sessions[0]["id"], [document["id"] for document in documents]
        )
        if not chunks:
            raise ValueError(f"Paper is not indexed: {paper_id}")
        digest = "\n\n".join(
            f"[Section: {chunk.metadata.section} | Chunk: {chunk.metadata.chunk_index}] {chunk.text[:1200]}"
            for chunk in chunks[:12]
        )
        with generation_timer("compare_paper", paper_id=paper_id):
            raw = runner.complete(
                _COMPARE_PROMPT.format(title=paper["title"], digest=digest)
            )
        fields = _parse_fields(raw)
        citation = (
            f" [Section: {chunks[0].metadata.section} | "
            f"Chunk: {chunks[0].metadata.chunk_index}]"
        )
        for field, value in fields.items():
            if value and value != "未提及" and "[Section:" not in value:
                fields[field] = value + citation
        results.append(
            {
                "paper_id": paper_id,
                "title": paper["title"],
                **fields,
            }
        )
    return results


def _parse_fields(raw: str) -> dict[str, str]:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        payload = {}
    return {
        field: str(payload.get(field) or "未提及")
        for field in ("method", "datasets", "metrics", "limitations")
    }
