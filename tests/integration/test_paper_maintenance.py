"""Maintenance scripts: hash backfill and duplicate paper merge."""

import hashlib

import pytest

from backend.domain.models import Chunk, ChunkMetadata
from backend.scripts import backfill_paper_hashes, merge_duplicate_papers
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.connection import connect


def _seed_paper(filename: str, *, file_hash: str | None, file_path: str) -> dict[str, str]:
    session = session_repo.create_session(filename, user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename=filename,
        file_path=file_path,
        mime_type="application/pdf",
        file_size=10,
        file_hash=file_hash,
    )
    return {
        "session_id": session["id"],
        "document_id": document["id"],
        "paper_id": document["paper_id"],
    }


@pytest.mark.integration
def test_backfill_hashes_from_disk(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7 hash me")
    seeded = _seed_paper("paper.pdf", file_hash=None, file_path=str(pdf))

    result = backfill_paper_hashes.run(apply=True)

    assert result == {"updated": 1, "missing": 0}
    with connect() as conn:
        row = conn.execute(
            "SELECT file_hash FROM documents WHERE id = ?", (seeded["document_id"],)
        ).fetchone()
    assert row["file_hash"] == hashlib.sha256(pdf.read_bytes()).hexdigest()


@pytest.mark.integration
def test_merge_duplicate_papers_moves_children():
    first = _seed_paper("first.pdf", file_hash="same-hash", file_path="/tmp/first.pdf")
    second = _seed_paper("second.pdf", file_hash="same-hash", file_path="/tmp/second.pdf")
    chunk_repo.insert_chunks(
        second["session_id"],
        second["document_id"],
        [
            Chunk(
                text="duplicate chunk",
                metadata=ChunkMetadata(
                    paper_id=second["document_id"],
                    section="Introduction",
                    chunk_index=0,
                    type="paragraph",
                ),
            )
        ],
    )
    annotation = annotation_repo.create_annotation(
        paper_id=second["paper_id"],
        annotation_type="note",
        content="duplicate note",
    )
    collection = collection_repo.create_collection(user_id="u1", name="Reading")
    collection_repo.add_paper_to_collection(collection["id"], second["paper_id"])
    with connect() as conn:
        conn.execute(
            "INSERT INTO paper_tags (paper_id, tag) VALUES (?, ?)",
            (second["paper_id"], "dup"),
        )

    groups = merge_duplicate_papers.find_duplicate_groups()
    assert len(groups) == 1
    assert set(groups[0]["paper_ids"]) == {first["paper_id"], second["paper_id"]}

    merge_duplicate_papers.merge_group(first["paper_id"], [second["paper_id"]])

    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) AS total FROM papers").fetchone()["total"] == 1
        assert conn.execute(
            "SELECT paper_id FROM documents WHERE id = ?", (second["document_id"],)
        ).fetchone()["paper_id"] == first["paper_id"]
        assert conn.execute(
            "SELECT paper_id FROM chunks WHERE document_id = ?", (second["document_id"],)
        ).fetchone()["paper_id"] == first["paper_id"]
        assert conn.execute(
            "SELECT paper_id FROM annotations WHERE id = ?", (annotation["id"],)
        ).fetchone()["paper_id"] == first["paper_id"]
        assert conn.execute(
            "SELECT paper_id FROM sessions WHERE id = ?", (second["session_id"],)
        ).fetchone()["paper_id"] == first["paper_id"]

    assert [row["id"] for row in collection_repo.list_collection_papers(collection["id"])] == [
        first["paper_id"]
    ]
    assert collection_repo.list_tags(first["paper_id"]) == ["dup"]
    assert paper_repo.get_paper(second["paper_id"]) is None
