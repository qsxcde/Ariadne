"""Session tool behaviour: retrieval scope, ACL and paper metadata."""

import json

import pytest

from backend.application.agent.tools import SessionTools
from backend.domain.models import Chunk, ChunkMetadata, VectorSearchHit
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo


class FakeStore:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def list_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def search(self, query: str, k: int = 5) -> list[Chunk]:
        return list(self._chunks[:k])

    def search_with_ranks(self, query: str, k: int = 5) -> list[VectorSearchHit]:
        return [
            VectorSearchHit(chunk=chunk, score=1.0, rank=index + 1)
            for index, chunk in enumerate(self._chunks[:k])
        ]


def _seed(texts: list[tuple[str, int, str]]) -> dict[str, str]:
    session = session_repo.create_session("Tools", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="Attention Paper.pdf",
        file_path="/tmp/attention.pdf",
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
    return {
        "session_id": session["id"],
        "document_id": document["id"],
        "paper_id": document["paper_id"],
    }


def _tools(seeded: dict[str, str]) -> SessionTools:
    chunks = chunk_repo.list_chunks(seeded["session_id"])
    return SessionTools(
        session_id=seeded["session_id"],
        user_id="u1",
        store=FakeStore(chunks),
        preview_chars=40,
        max_evidence_chars=500,
    )


def test_search_returns_scoped_sources(isolated_storage) -> None:
    seeded = _seed(
        [
            ("Introduction", 0, "Attention improves sequence modelling."),
            ("Method", 1, "We use sparse attention kernels."),
        ]
    )
    result = _tools(seeded).search_session_chunks("attention", top_k=2)

    assert result.ok
    assert "Attention Paper" in result.content
    assert "命中" in result.summary
    assert {source.section for source in result.sources} == {"Introduction", "Method"}
    assert all(source.paper_id == seeded["document_id"] for source in result.sources)


def test_search_accepts_real_paper_id_and_section_filter(isolated_storage) -> None:
    seeded = _seed(
        [
            ("Introduction", 0, "Attention improves sequence modelling."),
            ("Method", 1, "We use sparse attention kernels."),
        ]
    )
    tools = _tools(seeded)
    by_paper = tools.search_session_chunks("attention", paper_ids=[seeded["paper_id"]])
    by_section = tools.search_session_chunks("attention", section="Method")

    assert by_paper.ok and by_paper.sources
    assert {source.section for source in by_section.sources} == {"Method"}


def test_search_unknown_paper_returns_empty_result(isolated_storage) -> None:
    seeded = _seed([("Introduction", 0, "Attention improves sequence modelling.")])
    result = _tools(seeded).search_session_chunks("attention", paper_ids=["paper_missing"])

    assert result.ok
    assert result.sources == ()
    assert "没有可检索的论文" in result.content


def test_read_chunk_enforces_session_acl(isolated_storage) -> None:
    seeded = _seed([("Introduction", 0, "full text of the introduction")])
    tools = _tools(seeded)

    allowed = tools.read_chunk(seeded["document_id"], "Introduction", 0)
    assert allowed.ok
    assert "full text of the introduction" in allowed.content
    assert allowed.sources[0].chunk_index == 0

    denied = tools.read_chunk("document-from-another-session", "Introduction", 0)
    assert not denied.ok
    assert "无权访问" in (denied.error or "")


def test_get_paper_accepts_document_or_paper_id(isolated_storage) -> None:
    seeded = _seed([("Introduction", 0, "text")])
    tools = _tools(seeded)

    by_document = tools.get_paper(seeded["document_id"])
    by_paper = tools.get_paper(seeded["paper_id"])
    denied = tools.get_paper("paper_missing")

    assert by_document.ok and by_paper.ok
    assert json.loads(by_document.content)["title"] == "Attention Paper"
    assert json.loads(by_paper.content)["paper_id"] == seeded["paper_id"]
    assert not denied.ok


def test_tool_rejects_foreign_paper_even_if_it_exists(isolated_storage) -> None:
    seeded = _seed([("Introduction", 0, "text")])
    other_session = session_repo.create_session("Other", user_id="u1")
    other_document = document_repo.create_document(
        session_id=other_session["id"],
        filename="Other.pdf",
        file_path="/tmp/other.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    tools = _tools(seeded)

    result = tools.get_paper(other_document["paper_id"])
    assert not result.ok
    assert "当前会话" in (result.error or "")


@pytest.mark.parametrize("section", ["Missing"])
def test_read_chunk_missing_section_reports_failure(isolated_storage, section: str) -> None:
    seeded = _seed([("Introduction", 0, "text")])
    result = _tools(seeded).read_chunk(seeded["document_id"], section, 0)
    assert not result.ok
