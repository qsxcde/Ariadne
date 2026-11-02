"""Glossary generation and library stats."""

import json

import pytest

from backend.application.glossary import generate_glossary
from backend.application.stats import library_stats
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo


class FakeCompleter:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return json.dumps(self.payload, ensure_ascii=False)


def _seed() -> str:
    session = session_repo.create_session("Glossary", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="glossary.pdf",
        file_path="/tmp/glossary.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text="Sparse attention reduces computation.",
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
def test_glossary_uses_chunks_and_returns_terms():
    paper_id = _seed()
    fake = FakeCompleter(
        {
            "terms": [
                {
                    "term": "Sparse attention",
                    "definition": "只关注固定 token 集合的注意力",
                    "section": "Method",
                    "chunk_index": 0,
                }
            ]
        }
    )

    result = generate_glossary(paper_id, "u1", completer=fake)

    assert result["paper_id"] == paper_id
    assert result["terms"][0]["term"] == "Sparse attention"
    assert "Sparse attention" in fake.prompts[0]


@pytest.mark.unit
def test_glossary_rejects_unindexed_paper():
    session = session_repo.create_session("Empty", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="empty.pdf",
        file_path="/tmp/empty.pdf",
        mime_type="application/pdf",
        file_size=10,
    )

    with pytest.raises(ValueError, match="not indexed"):
        generate_glossary(document["paper_id"], "u1", completer=FakeCompleter({}))


@pytest.mark.integration
def test_library_stats_counts_status_notes_and_collections():
    paper_id = _seed()
    paper_repo.update_reading_state(paper_id, reading_status="read")
    annotation_repo.create_annotation(
        paper_id=paper_id, annotation_type="note", content="note"
    )
    annotation_repo.create_annotation(
        paper_id=paper_id, annotation_type="question", content="why"
    )
    collection = collection_repo.create_collection(user_id="u1", name="Topic")
    collection_repo.add_paper_to_collection(collection["id"], paper_id)

    stats = library_stats("u1")

    assert stats["total"] == 1
    assert stats["by_status"]["read"] == 1
    assert stats["notes"] == 1
    assert stats["questions"] == 1
    assert stats["collections"] == 1
