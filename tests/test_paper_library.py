"""Paper library, collections, tags and annotations (schema v8)."""

import pytest

from backend.application import collections as collection_service
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.connection import connect


def _seed_paper(
    *,
    session_title: str,
    user_id: str | None,
    filename: str,
    file_hash: str | None = None,
) -> dict[str, str]:
    session = session_repo.create_session(session_title, user_id=user_id)
    document = document_repo.create_document(
        session_id=session["id"],
        filename=filename,
        file_path=f"/tmp/{filename}",
        mime_type="application/pdf",
        file_size=100,
        file_hash=file_hash,
    )
    return {
        "session_id": session["id"],
        "document_id": document["id"],
        "paper_id": document["paper_id"],
    }


def _insert_chunk(session_id: str, document_id: str, text: str = "chunk text") -> str:
    chunk_repo.insert_chunks(
        session_id,
        document_id,
        [
            Chunk(
                text=text,
                metadata=ChunkMetadata(
                    paper_id=document_id,
                    section="Introduction",
                    chunk_index=0,
                    type="paragraph",
                ),
            )
        ],
    )
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM chunks WHERE document_id = ? ORDER BY chunk_index ASC LIMIT 1",
            (document_id,),
        ).fetchone()
    assert row is not None
    return str(row["id"])


@pytest.mark.integration
def test_list_papers_filters_by_user_status_text_collection_and_tag():
    mine = _seed_paper(
        session_title="Mine",
        user_id="u1",
        filename="Attention Is All You Need.pdf",
    )
    _seed_paper(session_title="Other", user_id="u2", filename="Other Paper.pdf")
    legacy = _seed_paper(
        session_title="Legacy", user_id=None, filename="Legacy Paper.pdf"
    )

    paper_repo.update_reading_state(mine["paper_id"], reading_status="reading", progress=0.4)

    mine_rows = paper_repo.list_papers("u1")
    assert [row["id"] for row in mine_rows] == [mine["paper_id"]]
    assert mine_rows[0]["reading_status"] == "reading"
    assert mine_rows[0]["progress"] == 0.4

    assert paper_repo.list_papers(None)[0]["id"] == legacy["paper_id"]
    assert paper_repo.list_papers("u1", reading_status="reading")[0]["id"] == mine["paper_id"]
    assert paper_repo.list_papers("u1", reading_status="read") == []
    assert paper_repo.list_papers("u1", query="attention")[0]["id"] == mine["paper_id"]
    assert paper_repo.list_papers("u1", query="missing") == []

    collection = collection_repo.create_collection(user_id="u1", name="Transformers")
    collection_repo.add_paper_to_collection(collection["id"], mine["paper_id"])
    assert [row["id"] for row in paper_repo.list_papers("u1", collection_id=collection["id"])] == [
        mine["paper_id"]
    ]
    assert paper_repo.list_papers("u1", collection_id="missing") == []

    collection_repo.add_tag(mine["paper_id"], "nlp")
    assert paper_repo.list_papers("u1", tag="nlp")[0]["id"] == mine["paper_id"]
    assert paper_repo.list_papers("u1", tag="cv") == []


@pytest.mark.integration
def test_reading_state_is_clamped_and_persisted():
    paper = _seed_paper(session_title="P", user_id="u1", filename="P.pdf")

    paper_repo.update_reading_state(
        paper["paper_id"],
        reading_status="reading",
        progress=2.5,
        last_location_json='{"page": 3}',
        time_spent_seconds=120,
    )
    row = paper_repo.get_paper(paper["paper_id"])
    assert row is not None
    assert row["reading_status"] == "reading"
    assert row["progress"] == 1.0
    assert row["last_location_json"] == '{"page": 3}'
    assert row["time_spent_seconds"] == 120

    paper_repo.update_reading_state(paper["paper_id"], progress=-1)
    row = paper_repo.get_paper(paper["paper_id"])
    assert row is not None and row["progress"] == 0.0

    with pytest.raises(ValueError):
        paper_repo.update_reading_state(paper["paper_id"], reading_status="unknown")


@pytest.mark.integration
def test_find_by_file_hash_is_scoped_to_user():
    mine = _seed_paper(
        session_title="Mine", user_id="u1", filename="Mine.pdf", file_hash="hash-1"
    )
    _seed_paper(
        session_title="Other", user_id="u2", filename="Other.pdf", file_hash="hash-1"
    )

    found = paper_repo.find_by_file_hash("u1", "hash-1")
    assert found is not None and found["id"] == mine["paper_id"]
    assert paper_repo.find_by_file_hash("u1", "hash-missing") is None
    assert paper_repo.find_by_file_hash(None, "hash-1") is None


@pytest.mark.integration
def test_collections_and_tags_round_trip():
    paper = _seed_paper(session_title="P", user_id="u1", filename="P.pdf")
    collection = collection_repo.create_collection(
        user_id="u1", name="Reading list", description="Q4"
    )

    collection_repo.add_paper_to_collection(collection["id"], paper["paper_id"])
    collection_repo.add_paper_to_collection(collection["id"], paper["paper_id"])

    assert [row["id"] for row in collection_repo.list_collections("u1")] == [collection["id"]]
    assert [row["id"] for row in collection_repo.list_collection_papers(collection["id"])] == [
        paper["paper_id"]
    ]
    assert [row["id"] for row in collection_repo.list_collections_for_paper(paper["paper_id"])] == [
        collection["id"]
    ]

    collection_repo.remove_paper_from_collection(collection["id"], paper["paper_id"])
    assert collection_repo.list_collection_papers(collection["id"]) == []

    collection_repo.add_tag(paper["paper_id"], "nlp")
    collection_repo.add_tag(paper["paper_id"], "nlp")
    collection_repo.add_tag(paper["paper_id"], "  ")
    assert collection_repo.list_tags(paper["paper_id"]) == ["nlp"]
    collection_repo.remove_tag(paper["paper_id"], "nlp")
    assert collection_repo.list_tags(paper["paper_id"]) == []


@pytest.mark.integration
def test_annotations_validate_anchor_and_round_trip():
    first = _seed_paper(session_title="First", user_id="u1", filename="First.pdf")
    second = _seed_paper(session_title="Second", user_id="u1", filename="Second.pdf")
    chunk_id = _insert_chunk(first["session_id"], first["document_id"], "important text")

    highlight = annotation_repo.create_annotation(
        paper_id=first["paper_id"],
        annotation_type="highlight",
        quote="important",
        chunk_id=chunk_id,
        color="yellow",
    )
    assert highlight["document_id"] == first["document_id"]
    assert highlight["chunk_id"] == chunk_id

    note = annotation_repo.create_annotation(
        paper_id=first["paper_id"],
        annotation_type="note",
        content="Remember this",
    )
    question = annotation_repo.create_annotation(
        paper_id=first["paper_id"],
        annotation_type="question",
        content="Why?",
    )
    assert [row["id"] for row in annotation_repo.list_annotations(first["paper_id"])] == [
        highlight["id"],
        note["id"],
        question["id"],
    ]
    assert [row["id"] for row in annotation_repo.list_annotations(first["paper_id"], annotation_type="note")] == [
        note["id"]
    ]

    updated = annotation_repo.update_annotation(note["id"], content="Updated")
    assert updated is not None and updated["content"] == "Updated"
    assert annotation_repo.delete_annotation(question["id"]) is True
    assert annotation_repo.get_annotation(question["id"]) is None

    with pytest.raises(ValueError):
        annotation_repo.create_annotation(
            paper_id=second["paper_id"],
            annotation_type="highlight",
            quote="important",
            chunk_id=chunk_id,
        )
    with pytest.raises(ValueError):
        annotation_repo.create_annotation(
            paper_id=first["paper_id"],
            annotation_type="highlight",
            quote="   ",
        )
    with pytest.raises(ValueError):
        annotation_repo.create_annotation(
            paper_id=first["paper_id"],
            annotation_type="note",
            content="   ",
        )


@pytest.mark.integration
def test_collection_summary_counts_reading_status():
    first = _seed_paper(session_title="A", user_id="u1", filename="a.pdf")
    second = _seed_paper(session_title="B", user_id="u1", filename="b.pdf")
    collection = collection_repo.create_collection(user_id="u1", name="Thesis")
    collection_repo.add_paper_to_collection(collection["id"], first["paper_id"])
    collection_repo.add_paper_to_collection(collection["id"], second["paper_id"])
    paper_repo.update_reading_state(first["paper_id"], reading_status="read")
    paper_repo.update_reading_state(second["paper_id"], reading_status="reading")

    summary = collection_service.list_for_user("u1")[0]
    assert summary["paper_count"] == 2
    assert summary["by_status"] == {"read": 1, "reading": 1}
