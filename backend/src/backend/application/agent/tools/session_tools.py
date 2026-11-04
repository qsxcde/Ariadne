"""Read-only tools over one session's indexed papers.

Pure Python: no LangChain imports and no HTTP types. The adapter wraps these
methods into framework tools, which keeps the business logic testable offline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from backend.config import settings
from backend.domain.access import paper_is_accessible
from backend.domain.agent import ToolResult
from backend.domain.models import Chunk, SourceRef
from backend.domain.ports import Reranker, VectorStore
from backend.rag.retrieval.hybrid_retriever import (
    HybridRetrievalOptions,
    retrieve_hybrid_context,
)
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


@dataclass(frozen=True, slots=True)
class _DocInfo:
    document_id: str
    paper_id: str
    title: str


class SessionTools:
    """Three read-only tools scoped to a single chat session."""

    def __init__(
        self,
        *,
        session_id: str,
        user_id: str | None,
        store: VectorStore,
        reranker: Reranker | None = None,
        preview_chars: int | None = None,
        max_evidence_chars: int | None = None,
    ) -> None:
        self._session_id = session_id
        self._user_id = user_id
        self._store = store
        self._reranker = reranker
        self._preview_chars = preview_chars or settings.agent_tool_preview_chars
        self._max_evidence_chars = max_evidence_chars or settings.agent_max_evidence_chars
        self._documents = self._load_session_documents()
        self._session = session_repo.get_session(session_id)

    def _load_session_documents(self) -> dict[str, _DocInfo]:
        documents = document_repo.list_documents(self._session_id)
        paper_titles: dict[str, str] = {}
        result: dict[str, _DocInfo] = {}
        for document in documents:
            paper_id = document["paper_id"]
            if paper_id not in paper_titles:
                paper = paper_repo.get_paper(paper_id)
                paper_titles[paper_id] = (
                    paper["title"] if paper and paper["title"] else document["filename"]
                )
            result[document["id"]] = _DocInfo(
                document_id=document["id"],
                paper_id=paper_id,
                title=paper_titles[paper_id],
            )
        return result

    def _allowed_document_ids(self) -> set[str]:
        return set(self._documents)

    def _allowed_paper_ids(self) -> set[str]:
        allowed = {info.paper_id for info in self._documents.values()}
        if self._session is not None and self._session.get("paper_id"):
            allowed.add(str(self._session["paper_id"]))
        return allowed

    def _resolve_document_ids(self, values: list[str]) -> set[str]:
        allowed = self._allowed_document_ids()
        resolved: set[str] = set()
        for value in values:
            if value in allowed:
                resolved.add(value)
                continue
            paper = paper_repo.get_paper(value)
            if paper is not None:
                for document in document_repo.list_documents_for_paper(value):
                    if document["session_id"] == self._session_id:
                        resolved.add(document["id"])
        return resolved

    def _resolve_paper_id(self, value: str | None) -> str | None:
        if value is None:
            if self._session is not None:
                return str(self._session["paper_id"]) if self._session.get("paper_id") else None
            return None
        paper = paper_repo.get_paper(value)
        if paper is not None:
            return value
        document = document_repo.get_document(value)
        if document is not None and document["session_id"] == self._session_id:
            return str(document["paper_id"])
        return None

    def _title_for_document(self, document_id: str) -> str:
        info = self._documents.get(document_id)
        return info.title if info else document_id

    def _source(self, chunk: Chunk) -> SourceRef:
        return SourceRef(
            paper_id=chunk.metadata.paper_id,
            section=chunk.metadata.section,
            chunk_index=chunk.metadata.chunk_index,
            text_excerpt=chunk.text[: self._preview_chars],
            page_start=chunk.metadata.page_start,
            page_end=chunk.metadata.page_end,
            block_ids=chunk.metadata.block_ids,
            confidence=chunk.metadata.confidence,
        )

    def _limit(self, text: str) -> str:
        if len(text) <= self._max_evidence_chars:
            return text
        return text[: self._max_evidence_chars].rstrip() + "\n…（证据已截断）"

    def search_session_chunks(
        self,
        query: str,
        paper_ids: list[str] | None = None,
        section: str | None = None,
        top_k: int = 5,
    ) -> ToolResult:
        limit = max(1, min(int(top_k), 10))
        document_ids = self._allowed_document_ids()
        if paper_ids:
            document_ids &= self._resolve_document_ids(paper_ids)
        if not document_ids:
            return ToolResult(
                ok=True,
                content="当前会话中没有可检索的论文。",
                summary="未命中",
            )

        options = HybridRetrievalOptions(
            bm25_top_k=limit,
            dense_top_k=limit,
            seed_top_k=limit,
            max_expanded_chunks=max(limit, 4),
            same_section_window=0,
            adjacent_window=0,
            include_linked_blocks=False,
            enable_reranker=self._reranker is not None,
            rerank_top_k=limit,
            history_rewrite_enabled=False,
            term_expand_enabled=False,
            document_ids=sorted(document_ids),
            section=section,
        )
        result = retrieve_hybrid_context(
            self._store,
            query,
            options=options,
            reranker=self._reranker,
        )
        chunks = [
            chunk
            for chunk in result.prompt_chunks
            if chunk.metadata.paper_id in document_ids
            and (section is None or chunk.metadata.section == section)
        ][:limit]
        if not chunks:
            scope = f"章节「{section}」内" if section else "当前会话中"
            return ToolResult(
                ok=True,
                content=f"{scope}未检索到与「{query}」相关的片段。",
                summary="未命中",
            )

        blocks = []
        for index, chunk in enumerate(chunks, start=1):
            pages = ""
            if chunk.metadata.page_start is not None:
                pages = f" | Pages: {chunk.metadata.page_start}-{chunk.metadata.page_end or chunk.metadata.page_start}"
            blocks.append(
                f"[{index}] {self._title_for_document(chunk.metadata.paper_id)}"
                f" | Section: {chunk.metadata.section}"
                f" | Chunk: {chunk.metadata.chunk_index}{pages}\n"
                f"{chunk.text[: self._preview_chars]}"
            )
        content = self._limit("\n\n".join(blocks))
        titles = "、".join(
            dict.fromkeys(self._title_for_document(chunk.metadata.paper_id) for chunk in chunks)
        )
        return ToolResult(
            ok=True,
            content=content,
            summary=f"命中 {len(chunks)} 个片段 · {titles[:80]}",
            sources=tuple(self._source(chunk) for chunk in chunks),
        )

    def read_chunk(self, paper_id: str, section: str, chunk_index: int) -> ToolResult:
        document_ids = self._resolve_document_ids([paper_id]) & self._allowed_document_ids()
        if not document_ids:
            return ToolResult.failure("该论文不在当前会话中，或无权访问。")

        chunks = [
            chunk
            for chunk in self._store.list_chunks()
            if chunk.metadata.paper_id in document_ids
            and chunk.metadata.section == section
            and chunk.metadata.chunk_index == chunk_index
        ]
        if not chunks:
            return ToolResult.failure(
                f"未找到指定片段：Section={section}，Chunk={chunk_index}。"
            )

        chunk = chunks[0]
        header = (
            f"{self._title_for_document(chunk.metadata.paper_id)}"
            f" | Section: {chunk.metadata.section}"
            f" | Chunk: {chunk.metadata.chunk_index}"
        )
        content = self._limit(f"{header}\n\n{chunk.text}")
        return ToolResult(
            ok=True,
            content=content,
            summary=(
                f"{self._title_for_document(chunk.metadata.paper_id)}"
                f" · {chunk.metadata.section} #{chunk.metadata.chunk_index}"
                f" · {len(chunk.text)} 字"
            ),
            sources=(self._source(chunk),),
        )

    def get_paper(self, paper_id: str | None = None) -> ToolResult:
        resolved = self._resolve_paper_id(paper_id)
        if resolved is None or resolved not in self._allowed_paper_ids():
            return ToolResult.failure("该论文不在当前会话中，或无权访问。")

        paper = paper_repo.get_paper(resolved)
        if paper is None or not paper_is_accessible(paper, self._user_id):
            return ToolResult.failure("论文不存在或无权访问。")

        authors: object = paper["authors_json"]
        if isinstance(authors, str):
            try:
                authors = json.loads(authors)
            except json.JSONDecodeError:
                authors = [authors]
        payload = {
            "paper_id": paper["id"],
            "title": paper["title"],
            "authors": authors,
            "year": paper["year"],
            "venue": paper["venue"],
            "doi": paper["doi"],
            "arxiv_id": paper["arxiv_id"],
            "abstract": (paper["abstract"] or "")[:2000],
        }
        return ToolResult(
            ok=True,
            content=json.dumps(payload, ensure_ascii=False),
            summary=str(paper["title"]),
        )
