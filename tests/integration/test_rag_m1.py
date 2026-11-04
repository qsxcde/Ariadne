"""M1 RAG core: history prompt, scoped retrieval and chunk citations."""

import pytest

from backend.domain.models import Chunk, ChunkMetadata
from backend.rag.answer import _answer_has_valid_chunk_citations
from backend.rag.retrieval.hybrid_retriever import (
    HybridRetrievalOptions,
    retrieve_hybrid_context,
)


def _chunk(
    *,
    document_id: str,
    section: str,
    index: int,
    text: str,
    chunk_type: str = "paragraph",
) -> Chunk:
    return Chunk(
        text=text,
        metadata=ChunkMetadata(
            paper_id=document_id,
            section=section,
            section_path=[section],
            chunk_index=index,
            type=chunk_type,
        ),
    )


@pytest.mark.unit
def test_prompt_includes_prior_history_and_skips_current_question():
    from backend.adapters.llm.prompt_template import build_prompt

    prompt = build_prompt(
        [_chunk(document_id="d1", section="Method", index=0, text="method text")],
        "它的参数量是多少？",
        history=[
            {"role": "user", "content": "这篇论文的方法是什么？"},
            {"role": "assistant", "content": "它提出了一个稀疏注意力方法。"},
            {"role": "user", "content": "它的参数量是多少？"},
        ],
    )

    assert "稀疏注意力方法" in prompt
    assert "对话历史" in prompt
    assert prompt.count("它的参数量是多少？") == 1


@pytest.mark.unit
def test_chunk_citations_require_matching_section_and_index():
    chunks = [
        _chunk(document_id="d1", section="Method", index=3, text="method"),
        _chunk(document_id="d1", section="Experiments", index=7, text="results"),
    ]

    assert _answer_has_valid_chunk_citations(
        "结论 [Section: Method | Chunk: 3]", chunks
    )
    assert _answer_has_valid_chunk_citations("结论 [Section: Method]", chunks)
    assert not _answer_has_valid_chunk_citations(
        "结论 [Section: Method | Chunk: 7]", chunks
    )
    assert not _answer_has_valid_chunk_citations(
        "结论 [Section: Missing | Chunk: 3]", chunks
    )
    assert not _answer_has_valid_chunk_citations("没有引用", chunks)


@pytest.mark.integration
def test_hybrid_retrieval_respects_document_section_and_type_scope():
    pytest.importorskip("torch", reason="reranker imports torch")
    chunks = [
        _chunk(document_id="d1", section="Method", index=0, text="method alpha"),
        _chunk(document_id="d1", section="Experiments", index=1, text="table alpha", chunk_type="table"),
        _chunk(document_id="d2", section="Method", index=0, text="method beta"),
    ]

    class FakeStore:
        def list_chunks(self):
            return chunks

    base = dict(
        bm25_top_k=10,
        dense_top_k=0,
        seed_top_k=10,
        max_expanded_chunks=10,
        same_section_window=0,
        adjacent_window=0,
        include_linked_blocks=False,
        enable_reranker=False,
        history_rewrite_enabled=False,
        term_expand_enabled=False,
    )

    by_document = retrieve_hybrid_context(
        FakeStore(),
        "method",
        options=HybridRetrievalOptions(document_ids=["d2"], **base),
    )
    assert {chunk.metadata.paper_id for chunk in by_document.prompt_chunks} == {"d2"}

    by_section = retrieve_hybrid_context(
        FakeStore(),
        "alpha",
        options=HybridRetrievalOptions(section="Experiments", **base),
    )
    assert {chunk.metadata.section for chunk in by_section.prompt_chunks} == {"Experiments"}

    by_type = retrieve_hybrid_context(
        FakeStore(),
        "alpha",
        options=HybridRetrievalOptions(chunk_types=["table"], **base),
    )
    assert {chunk.metadata.type for chunk in by_type.prompt_chunks} == {"table"}
