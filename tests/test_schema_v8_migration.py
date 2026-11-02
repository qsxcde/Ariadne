"""Schema v8 migration: old sessions/documents keep working and gain paper links."""

import sqlite3

import pytest

from backend import config
from backend.domain.models import Chunk, ChunkMetadata
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import jobs as job_repo
from backend.storage.sqlite import sessions as session_repo
from backend.storage.sqlite.schema import init_db

V7_SCHEMA = """
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  hashed_password TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  user_id TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_opened_at TEXT NOT NULL,
  is_archived INTEGER NOT NULL DEFAULT 0,
  is_pinned INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size INTEGER NOT NULL,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL,
  error_message TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  parsed_ir_path TEXT NULL,
  parsed_markdown_path TEXT NULL,
  quality_report_path TEXT NULL,
  parser_name TEXT NULL,
  parser_version TEXT NULL,
  parse_quality_status TEXT NULL
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  sources_json TEXT NULL,
  status TEXT NOT NULL,
  client_message_id TEXT NULL,
  model TEXT NULL,
  prompt_tokens INTEGER NULL,
  completion_tokens INTEGER NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  section TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text_excerpt TEXT NOT NULL,
  text_content TEXT NOT NULL,
  type TEXT NOT NULL,
  created_at TEXT NOT NULL,
  section_path_json TEXT NULL,
  page_start INTEGER NULL,
  page_end INTEGER NULL,
  bbox_json TEXT NULL,
  block_ids_json TEXT NULL,
  block_types_json TEXT NULL,
  linked_block_ids_json TEXT NULL,
  confidence REAL NULL
);

CREATE TABLE retrieval_indexes (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  index_path TEXT NOT NULL,
  chunks_path TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  document_id TEXT NULL REFERENCES documents(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  payload_json TEXT NULL,
  created_at TEXT NOT NULL,
  started_at TEXT NULL,
  finished_at TEXT NULL
);

CREATE TABLE index_snapshots (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  index_path TEXT NOT NULL,
  chunks_path TEXT NOT NULL,
  document_ids_json TEXT NOT NULL,
  error_message TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""

V7_SEED = """
INSERT INTO users VALUES ('u1', 'alice', 'x', '2026-01-01', '2026-01-01');
INSERT INTO sessions VALUES
  ('s1', 'Legacy session', 'u1', '2026-01-01T00:00:00+00:00',
   '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', 0, 0);
INSERT INTO documents VALUES
  ('doc-1', 's1', 'paper-one.pdf', '/tmp/paper-one.pdf', 'application/pdf', 100,
   1, 'ready', NULL, '2026-01-01T00:00:01+00:00', '2026-01-01T00:00:02+00:00',
   '/tmp/ir1.json', '/tmp/md1.md', '/tmp/q1.json', 'mineru', '1.0', 'ok'),
  ('doc-2', 's1', 'paper-two.pdf', '/tmp/paper-two.pdf', 'application/pdf', 200,
   1, 'uploaded', NULL, '2026-01-01T00:00:03+00:00', '2026-01-01T00:00:04+00:00',
   NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO chunks VALUES
  ('c1', 's1', 'doc-1', 'Introduction', 0, 'excerpt 1', 'text 1', 'paragraph',
   '2026-01-01T00:00:05+00:00', '["Introduction"]', 1, 1, NULL, NULL, NULL, NULL, 0.9),
  ('c2', 's1', 'doc-2', 'Method', 0, 'excerpt 2', 'text 2', 'paragraph',
   '2026-01-01T00:00:06+00:00', '["Method"]', 2, 2, NULL, NULL, NULL, NULL, 0.8);
INSERT INTO messages VALUES
  ('m1', 's1', 'user', 'hello', NULL, 'done', NULL, NULL, NULL, NULL,
   '2026-01-01T00:00:07+00:00');
INSERT INTO jobs VALUES
  ('j1', 's1', 'doc-1', 'document_ingestion', 'succeeded', 'ready', 1,
   NULL, '{}', '2026-01-01T00:00:08+00:00', '2026-01-01T00:00:09+00:00',
   '2026-01-01T00:00:10+00:00');
INSERT INTO retrieval_indexes VALUES
  ('ri1', 's1', '/tmp/index', '/tmp/chunks', 'ready',
   '2026-01-01T00:00:11+00:00', '2026-01-01T00:00:11+00:00');
INSERT INTO index_snapshots VALUES
  ('snap1', 's1', 'ready', '/tmp/index', '/tmp/chunks', '["doc-1"]', NULL,
   '2026-01-01T00:00:12+00:00', '2026-01-01T00:00:12+00:00');
"""


def _create_v7_db(path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(V7_SCHEMA)
        conn.executescript(V7_SEED)
        conn.execute("PRAGMA user_version = 7")
        conn.commit()
    finally:
        conn.close()


def _row(path, sql: str, params: tuple = ()):
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


@pytest.mark.integration
def test_v7_database_migrates_to_papers(tmp_path, monkeypatch):
    db_path = tmp_path / "v7.db"
    _create_v7_db(db_path)
    monkeypatch.setattr(config.settings, "scipal_db_path", str(db_path))

    init_db()

    assert _row(db_path, "PRAGMA user_version")[0][0] == 9
    papers = _row(db_path, "SELECT * FROM papers ORDER BY id")
    assert [row["id"] for row in papers] == ["paper_doc-1", "paper_doc-2"]
    assert [row["title"] for row in papers] == ["paper-one", "paper-two"]
    assert {row["user_id"] for row in papers} == {"u1"}
    assert {row["reading_status"] for row in papers} == {"inbox"}

    documents = _row(db_path, "SELECT id, paper_id, file_hash FROM documents ORDER BY id")
    assert [row["paper_id"] for row in documents] == ["paper_doc-1", "paper_doc-2"]
    assert [row["file_hash"] for row in documents] == [None, None]

    chunk_rows = _row(db_path, "SELECT paper_id FROM chunks ORDER BY id")
    assert [row["paper_id"] for row in chunk_rows] == ["paper_doc-1", "paper_doc-2"]

    job_rows = _row(db_path, "SELECT paper_id FROM jobs")
    assert [row["paper_id"] for row in job_rows] == ["paper_doc-1"]

    session = _row(db_path, "SELECT paper_id FROM sessions WHERE id = 's1'")[0]
    assert session["paper_id"] == "paper_doc-1"

    assert _row(db_path, "SELECT COUNT(*) FROM messages")[0][0] == 1
    assert _row(db_path, "SELECT COUNT(*) FROM index_snapshots")[0][0] == 1
    assert _row(db_path, "SELECT COUNT(*) FROM subscriptions")[0][0] == 0
    assert _row(db_path, "SELECT COUNT(*) FROM feed_items")[0][0] == 0
    assert _row(db_path, "PRAGMA foreign_key_check") == []


@pytest.mark.integration
def test_v8_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "v7.db"
    _create_v7_db(db_path)
    monkeypatch.setattr(config.settings, "scipal_db_path", str(db_path))

    init_db()
    init_db()

    assert _row(db_path, "SELECT COUNT(*) FROM papers")[0][0] == 2
    assert _row(db_path, "SELECT COUNT(*) FROM documents")[0][0] == 2
    assert _row(db_path, "SELECT COUNT(*) FROM chunks")[0][0] == 2


@pytest.mark.unit
def test_new_document_creates_paper_and_propagates_it(tmp_path, monkeypatch):
    db_path = tmp_path / "fresh.db"
    monkeypatch.setattr(config.settings, "scipal_db_path", str(db_path))
    init_db()

    session = session_repo.create_session("New paper", user_id="u1")
    document = document_repo.create_document(
        session_id=session["id"],
        filename="new-paper.pdf",
        file_path="/tmp/new-paper.pdf",
        mime_type="application/pdf",
        file_size=10,
    )
    assert document["paper_id"] == f"paper_{document['id']}"
    assert session_repo.get_session(session["id"])["paper_id"] == document["paper_id"]

    chunk_repo.insert_chunks(
        session["id"],
        document["id"],
        [
            Chunk(
                text="hello",
                metadata=ChunkMetadata(
                    paper_id=document["id"],
                    section="Introduction",
                    chunk_index=0,
                    type="paragraph",
                ),
            )
        ],
    )
    job = job_repo.create_job(
        session_id=session["id"],
        document_id=document["id"],
        job_type="document_ingestion",
        stage="uploaded",
    )
    assert _row(db_path, "SELECT paper_id FROM chunks")[0][0] == document["paper_id"]
    assert job["paper_id"] == document["paper_id"]
