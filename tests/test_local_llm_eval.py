"""Real local-model baseline: Qwen2.5-3B + nomic-embed via Docker Ollama."""

import os

import pytest

from backend import composition
from backend.application.synthesis import compare_papers
from backend.domain.models import Chunk, ChunkMetadata
from backend.rag.answer import AnswerPolicy, RetrievalOptions, stream_answer
from backend.rag.indexing.vector_store import FAISSVectorStore
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo

pytestmark = [
    pytest.mark.local_llm,
    pytest.mark.skipif(
        os.getenv("SCIPAL_LOCAL_LLM") != "1",
        reason="run scripts/run_local_llm_eval.sh",
    ),
]

CASES = [
    ("How many tokens does SparseAttention use?", ["64"]),
    ("How much does SparseAttention improve BLEU on WMT?", ["1.2"]),
    ("What is the main limitation of SparseAttention?", ["long-range", "长程", "依赖"]),
    ("How much memory does SparseAttention save?", ["40", "百分之四十"]),
    ("What is the method called?", ["SparseAttention"]),
]


def _store() -> FAISSVectorStore:
    chunks = [
        Chunk(
            text="SparseAttention uses a fixed set of 64 tokens and reduces memory by 40%.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Method",
                section_path=["Method"],
                chunk_index=0,
                type="paragraph",
            ),
        ),
        Chunk(
            text="On WMT English-German, SparseAttention improves BLEU by 1.2 points.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Experiments",
                section_path=["Experiments"],
                chunk_index=1,
                type="paragraph",
            ),
        ),
        Chunk(
            text="A limitation is that the fixed token set may miss long-range dependencies.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Limitations",
                section_path=["Limitations"],
                chunk_index=2,
                type="paragraph",
            ),
        ),
    ]
    store = FAISSVectorStore(embed_fn=composition.embedder(), embedding_dim=768)
    store.add_chunks(chunks)
    return store


@pytest.mark.integration
def test_local_model_answers_with_citations():
    store = _store()
    policy = AnswerPolicy(
        empty_retrieval_message="没有相关信息", invalid_citation_message="引用无效"
    )
    options = RetrievalOptions(
        strategy="hybrid",
        bm25_top_k=5,
        dense_top_k=5,
        seed_top_k=5,
        max_expanded_chunks=5,
        same_section_window=0,
        adjacent_window=1,
        include_linked_blocks=False,
        enable_reranker=False,
        history_rewrite_enabled=False,
        term_expand_enabled=False,
    )

    correct = 0
    cited = 0
    for question, expected_terms in CASES:
        answer = ""
        for event in stream_answer(store, question, policy=policy, options=options):
            if event["type"] == "token":
                answer += event["value"]
        lowered = answer.lower()
        if any(term.lower() in lowered for term in expected_terms):
            correct += 1
        if "[Section:" in answer:
            cited += 1

    assert correct >= 4, f"local model answered {correct}/{len(CASES)} correctly"
    assert cited >= 4, f"local model cited {cited}/{len(CASES)} answers"


def _seed_paper(title: str, method: str, metric: str) -> str:
    session = session_repo.create_session(title, user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename=title + ".pdf",
        file_path=f"/tmp/{title}.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text=method,
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Method",
                    section_path=["Method"],
                    chunk_index=0,
                    type="paragraph",
                ),
            ),
            Chunk(
                text=metric,
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Experiments",
                    section_path=["Experiments"],
                    chunk_index=1,
                    type="paragraph",
                ),
            ),
        ],
    )
    return document["paper_id"]


@pytest.mark.integration
def test_local_model_compares_two_papers():
    first = _seed_paper(
        "PaperA",
        "Paper A proposes SparseAttention with 64 tokens.",
        "Paper A reports BLEU 1.2 on WMT.",
    )
    second = _seed_paper(
        "PaperB",
        "Paper B proposes DenseAttention with full attention.",
        "Paper B reports BLEU 0.8 on WMT.",
    )
    collection = collection_repo.create_collection(user_id="u1", name="Compare")
    collection_repo.add_paper_to_collection(collection["id"], first)
    collection_repo.add_paper_to_collection(collection["id"], second)

    rows = compare_papers(collection["id"], "u1", [first, second])

    assert len(rows) == 2
    assert all("[Section:" in row["method"] for row in rows)
    assert "Sparse" in rows[0]["method"]
    assert "1.2" in rows[0]["metrics"]
