import os
import sqlite3
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.scripts.migrate_sqlite_to_postgres import (
    MigrationError,
    run_migration,
)
from backend.storage.sqlite.schema import (
    CURRENT_SCHEMA_VERSION,
    _create_initial_schema,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not TEST_DATABASE_URL,
        reason="TEST_DATABASE_URL is not configured",
    ),
]


def _create_source(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _create_initial_schema(conn)
    conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
    conn.execute(
        "INSERT INTO users (id, username, hashed_password, created_at, updated_at) "
        "VALUES ('u1', 'alice', 'hash', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        """
        INSERT INTO papers (
          id, user_id, title, authors_json, year, doi, reading_status, progress,
          time_spent_seconds, created_at, updated_at
        ) VALUES (
          'p1', 'u1', 'Attention Is All You Need', '["Vaswani"]', 2017,
          '10.1000/abc', 'reading', 0.5, 120, '2026-01-01', '2026-01-02'
        )
        """
    )
    conn.execute(
        "INSERT INTO sessions (id, title, user_id, created_at, updated_at, last_opened_at) "
        "VALUES ('s1', 'Session', 'u1', '2026-01-01', '2026-01-01', '2026-01-01')"
    )
    conn.execute(
        """
        INSERT INTO documents (
          id, paper_id, session_id, filename, file_path, mime_type, file_size,
          status, created_at, updated_at
        ) VALUES (
          'd1', 'p1', 's1', 'paper.pdf', 'raw/s1/paper.pdf', 'application/pdf',
          1024, 'ready', '2026-01-01', '2026-01-01'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO chunks (
          id, paper_id, session_id, document_id, section, chunk_index,
          text_excerpt, text_content, type, created_at, confidence
        ) VALUES (
          'c1', 'p1', 's1', 'd1', 'Introduction', 0, 'excerpt', 'content',
          'text', '2026-01-01', 0.75
        )
        """
    )
    conn.execute(
        "INSERT INTO agent_runs (id, session_id, user_id, status, created_at) "
        "VALUES ('r1', 's1', 'u1', 'succeeded', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO agent_steps (id, run_id, step_index, kind, status, created_at) "
        "VALUES ('st1', 'r1', 0, 'answer', 'succeeded', '2026-01-01')"
    )
    conn.commit()
    return conn


def _target_rows(table: str) -> list[dict]:
    with psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row) as conn:
        return conn.execute(f'SELECT * FROM "{table}"').fetchall()


def test_migrates_all_tables_and_verifies_checksums(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source(source_path).close()

    report = run_migration(
        sqlite_path=source_path,
        database_url=TEST_DATABASE_URL,
        truncate=True,
    )

    assert report["checksums_ok"] is True
    assert report["tables"]["papers"]["source"] == 1
    assert report["tables"]["chunks"]["target_after"] == 1
    assert not any(report["target_orphans"].values())

    papers = _target_rows("papers")
    assert papers[0]["title"] == "Attention Is All You Need"
    assert papers[0]["progress"] == 0.5
    assert _target_rows("agent_steps")[0]["run_id"] == "r1"


def test_dry_run_writes_no_rows(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source(source_path).close()

    report = run_migration(
        sqlite_path=source_path,
        database_url=TEST_DATABASE_URL,
        dry_run=True,
    )

    assert report["tables"]["papers"]["source"] == 1
    assert report["tables"]["papers"]["target_after"] == 0
    assert _target_rows("papers") == []


def test_requires_truncate_when_target_is_populated(tmp_path):
    source_path = tmp_path / "source.db"
    _create_source(source_path).close()
    run_migration(
        sqlite_path=source_path,
        database_url=TEST_DATABASE_URL,
        truncate=True,
    )

    with pytest.raises(MigrationError, match="--truncate"):
        run_migration(
            sqlite_path=source_path,
            database_url=TEST_DATABASE_URL,
        )

    report = run_migration(
        sqlite_path=source_path,
        database_url=TEST_DATABASE_URL,
        truncate=True,
    )
    assert report["tables"]["papers"]["target_after"] == 1


def test_failed_import_rolls_back_truncate(tmp_path):
    source_path = tmp_path / "source.db"
    source = _create_source(source_path)
    run_migration(
        sqlite_path=source_path,
        database_url=TEST_DATABASE_URL,
        truncate=True,
    )

    source.execute(
        """
        INSERT INTO papers (id, user_id, title, year, reading_status, progress,
                            time_spent_seconds, created_at, updated_at)
        VALUES ('p2', 'u1', 'Broken Year', 'not-a-year', 'inbox', 0, 0,
                '2026-01-01', '2026-01-01')
        """
    )
    source.commit()
    source.close()

    with pytest.raises(psycopg.Error):
        run_migration(
            sqlite_path=source_path,
            database_url=TEST_DATABASE_URL,
            truncate=True,
        )

    papers = _target_rows("papers")
    assert [paper["id"] for paper in papers] == ["p1"]


def test_rejects_source_with_orphans(tmp_path):
    source_path = tmp_path / "source.db"
    source = _create_source(source_path)
    source.execute("PRAGMA foreign_keys = OFF")
    source.execute(
        """
        INSERT INTO documents (
          id, paper_id, session_id, filename, file_path, mime_type, file_size,
          status, created_at, updated_at
        ) VALUES (
          'd-orphan', 'missing', 's1', 'x.pdf', 'raw/x.pdf', 'application/pdf',
          1, 'ready', '2026-01-01', '2026-01-01'
        )
        """
    )
    source.commit()
    source.close()

    with pytest.raises(MigrationError, match="violates foreign keys"):
        run_migration(
            sqlite_path=source_path,
            database_url=TEST_DATABASE_URL,
            truncate=True,
        )
