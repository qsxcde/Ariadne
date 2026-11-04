"""Real local-model baseline: Qwen2.5-3B + nomic-embed via Docker Ollama."""

import os

import pytest

from backend import composition
from backend.application.synthesis.service import compare_papers
from backend.domain.models import Chunk, ChunkMetadata
from backend.rag.answer import AnswerPolicy, RetrievalOptions, stream_answer
from backend.adapters.vector.faiss_store import FAISSVectorStore
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

BASE_CASES = [
    ("What is the method called?", ["SparseAttention"]),
    ("How many tokens does SparseAttention use?", ["64"]),
    ("How much memory does SparseAttention save?", ["40", "百分之四十"]),
    ("Which dataset is used for experiments?", ["WMT", "English-German", "英德"]),
    ("How much does BLEU improve on WMT?", ["1.2"]),
    ("How many transformer layers does the model have?", ["12"]),
    ("How many GPUs were used for training?", ["8"]),
    ("What is the computational complexity?", ["O(n)", "linear", "线性"]),
    ("What license is the code released under?", ["MIT"]),
    ("What is the main limitation?", ["long-range", "长程", "依赖"]),
]

PHRASES = [
    "{q}",
    "According to the paper, {q}",
    "Please answer briefly based on the paper: {q}",
    "In the paper, {q}",
    "Answer this question using the paper: {q}",
]


def _store() -> FAISSVectorStore:
    chunks = [
        Chunk(
            text="The method is called SparseAttention. Token count: 64. Memory saving: 40%.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Method",
                section_path=["Method"],
                chunk_index=0,
                type="paragraph",
            ),
        ),
        Chunk(
            text="Dataset: WMT English-German. BLEU improvement: 1.2 points.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Experiments",
                section_path=["Experiments"],
                chunk_index=1,
                type="paragraph",
            ),
        ),
        Chunk(
            text="Layer count: 12. GPU count: 8.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Architecture",
                section_path=["Architecture"],
                chunk_index=2,
                type="paragraph",
            ),
        ),
        Chunk(
            text="Complexity: O(n).",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Complexity",
                section_path=["Complexity"],
                chunk_index=3,
                type="paragraph",
            ),
        ),
        Chunk(
            text="License: MIT.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="License",
                section_path=["License"],
                chunk_index=4,
                type="paragraph",
            ),
        ),
        Chunk(
            text="Limitation: may miss long-range dependencies.",
            metadata=ChunkMetadata(
                paper_id="doc-1",
                section="Limitations",
                section_path=["Limitations"],
                chunk_index=5,
                type="paragraph",
            ),
        ),
    ]
    store = FAISSVectorStore(embed_fn=composition.embedder(), embedding_dim=768)
    store.add_chunks(chunks)
    return store


def _options() -> RetrievalOptions:
    return RetrievalOptions(
        strategy="hybrid",
        bm25_top_k=8,
        dense_top_k=8,
        seed_top_k=8,
        max_expanded_chunks=8,
        same_section_window=0,
        adjacent_window=1,
        include_linked_blocks=False,
        enable_reranker=False,
        history_rewrite_enabled=False,
        term_expand_enabled=False,
    )


@pytest.mark.integration
def test_local_model_answers_50_questions_with_citations():
    store = _store()
    policy = AnswerPolicy(
        empty_retrieval_message="没有相关信息", invalid_citation_message="引用无效"
    )
    options = _options()

    correct = 0
    cited = 0
    total = 0
    for question, expected_terms in BASE_CASES:
        for phrase in PHRASES:
            prompt = phrase.format(q=question)
            answer = ""
            for event in stream_answer(store, prompt, policy=policy, options=options):
                if event["type"] == "token":
                    answer += event["value"]
            lowered = answer.lower()
            if any(term.lower() in lowered for term in expected_terms):
                correct += 1
            if "[Section:" in answer:
                cited += 1
            total += 1

    assert total == 50
    assert correct >= 45, f"local model answered {correct}/50 correctly"
    assert cited >= 45, f"local model cited {cited}/50 answers"


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
def test_local_model_compares_ten_papers():
    paper_ids = []
    for index in range(1, 11):
        paper_ids.append(
            _seed_paper(
                f"Paper{index}",
                f"Paper {index} proposes Method{index} for efficient attention.",
                f"Paper {index} reports BLEU 1.{index} on WMT.",
            )
        )
    collection = collection_repo.create_collection(user_id="u1", name="Compare")
    for paper_id in paper_ids:
        collection_repo.add_paper_to_collection(collection["id"], paper_id)

    rows = compare_papers(
        collection["id"], "u1", paper_ids, completer=composition.text_completer()
    )

    assert len(rows) == 10
    for index, row in enumerate(rows, start=1):
        assert f"Method{index}" in row["method"]
        assert "[Section:" in row["method"]
        assert f"1.{index}" in row["metrics"]
