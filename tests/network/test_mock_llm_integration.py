"""Integration tests against the Docker OpenAI-compatible mock service."""

import os

import pytest

from backend.application.reading.brief import generate_paper_brief
from backend.application.reading.explain import explain_selection
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import sessions as session_repo

pytestmark = [
    pytest.mark.mock_llm,
    pytest.mark.skipif(
        os.getenv("ARIADNE_MOCK_LLM") != "1",
        reason="set ARIADNE_MOCK_LLM=1 and start docker-compose.test.yml",
    ),
]


def _seed() -> str:
    session = session_repo.create_session("Mock paper", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="mock.pdf",
        file_path="/tmp/mock.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text="We propose a mock method for testing.",
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Method",
                    section_path=["Method"],
                    chunk_index=0,
                    type="paragraph",
                ),
            ),
            Chunk(
                text="Experiments run on a mock benchmark.",
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
def test_mock_llm_complete_and_embedding():
    from backend import composition

    answer = composition.text_completer().complete("hello")
    assert "mock" in answer.lower() or "模拟" in answer

    vectors = composition.embedder()(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 8


@pytest.mark.integration
def test_brief_and_explain_over_real_http():
    from backend import composition

    paper_id = _seed()

    completer = composition.text_completer()
    brief = generate_paper_brief(paper_id, "u1", completer=completer)
    assert brief["tldr"] == "Docker mock 速读卡"
    assert brief["sections"]

    translation = explain_selection(
        paper_id,
        "u1",
        text="We propose a mock method.",
        mode="translate",
        completer=completer,
    )
    assert "mock 翻译" in translation


@pytest.mark.integration
def test_chat_stream_over_real_http():
    from backend.adapters.llm.llm import stream_completion_tokens

    text = "".join(stream_completion_tokens("请回答一个测试问题"))
    assert text
    assert "mock" in text.lower() or "模拟" in text
