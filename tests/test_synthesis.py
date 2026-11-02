"""Collection-level Q&A and comparison."""

import json

import pytest

from backend.application.synthesis import answer_collection, compare_papers
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo


class FakeCompleter:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.payload


def _paper(title: str, text: str) -> str:
    session = session_repo.create_session(title, user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename=f"{title}.pdf",
        file_path=f"/tmp/{title}.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text=text,
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Method",
                    section_path=["Method"],
                    chunk_index=0,
                    type="paragraph",
                ),
            )
        ],
    )
    return document["paper_id"]


@pytest.mark.integration
def test_collection_answer_uses_papers_and_returns_real_paper_ids():
    pytest.importorskip("torch", reason="hybrid retriever imports torch")
    first = _paper("First", "We propose a sparse attention method.")
    second = _paper("Second", "We compare the method on WMT benchmarks.")
    collection = collection_repo.create_collection(user_id="u1", name="Topic")
    collection_repo.add_paper_to_collection(collection["id"], first)
    collection_repo.add_paper_to_collection(collection["id"], second)

    fake = FakeCompleter("综合答案 [Section: Method | Chunk: 0]")
    result = answer_collection(
        collection["id"], "u1", "compare the method", completer=fake
    )

    assert result["answer"].startswith("综合答案")
    assert set(result["paper_ids"]) == {first, second}
    assert result["chunk_count"] >= 1
    assert "First" not in fake.prompts[0]


@pytest.mark.integration
def test_compare_papers_returns_uniform_fields():
    first = _paper("First", "We propose sparse attention.")
    second = _paper("Second", "We evaluate on WMT.")
    collection = collection_repo.create_collection(user_id="u1", name="Topic")
    collection_repo.add_paper_to_collection(collection["id"], first)
    collection_repo.add_paper_to_collection(collection["id"], second)

    fake = FakeCompleter(
        json.dumps(
            {
                "method": "sparse attention [Section: Method | Chunk: 0]",
                "datasets": "未提及",
                "metrics": "BLEU",
                "limitations": "未提及",
            },
            ensure_ascii=False,
        )
    )

    rows = compare_papers(collection["id"], "u1", [first], completer=fake)

    assert rows[0]["paper_id"] == first
    assert "BLEU" in rows[0]["metrics"]
    assert "[Section:" in rows[0]["metrics"]
    assert rows[0]["limitations"] == "未提及"
