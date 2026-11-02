"""Paper brief generation: section digest + citation-bearing JSON."""

import json

import pytest

from backend.application.brief import generate_paper_brief
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo


def _seed(texts: list[tuple[str, int, str]]) -> dict[str, str]:
    session = session_repo.create_session("Brief", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="brief.pdf",
        file_path="/tmp/brief.pdf",
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
                    section=section,
                    section_path=[section],
                    chunk_index=index,
                    type="paragraph",
                ),
            )
            for section, index, text in texts
        ],
    )
    return {"paper_id": document["paper_id"], "document_id": document["id"]}


class FakeCompleter:
    def __init__(self, payload: dict):
        self.payload = payload
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return json.dumps(self.payload, ensure_ascii=False)


@pytest.mark.integration
def test_brief_uses_section_digest_and_returns_structured_fields():
    seeded = _seed(
        [
            ("Introduction", 0, "This paper studies attention."),
            ("Method", 1, "We propose sparse attention."),
            ("Experiments", 2, "We evaluate on WMT."),
        ]
    )
    fake = FakeCompleter(
        {
            "tldr": "稀疏注意力论文",
            "contributions": ["提出稀疏注意力 [Section: Method | Chunk: 1]"],
            "method": "稀疏注意力 [Section: Method | Chunk: 1]",
            "experiments": "WMT [Section: Experiments | Chunk: 2]",
            "limitations": "未提及",
            "takeaways": ["先读方法"],
            "sections": [
                {"title": "Method", "summary": "方法摘要", "chunk_indexes": [1]}
            ],
        }
    )

    brief = generate_paper_brief(seeded["paper_id"], "u1", completer=fake)

    assert brief["tldr"] == "稀疏注意力论文"
    assert brief["method"].startswith("稀疏注意力")
    assert brief["sections"][0]["summary"] == "方法摘要"
    assert "[Section: Method | Chunk: 1]" in fake.prompts[0]
    assert "Introduction" in fake.prompts[0]


@pytest.mark.integration
def test_brief_rejects_unindexed_paper():
    session = session_repo.create_session("Empty", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="empty.pdf",
        file_path="/tmp/empty.pdf",
        mime_type="application/pdf",
        file_size=10,
    )

    with pytest.raises(ValueError, match="not indexed"):
        generate_paper_brief(document["paper_id"], "u1", completer=FakeCompleter({}))
