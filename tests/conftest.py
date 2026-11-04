"""Shared fixtures: isolated metadata and data storage for every test."""

import os

import pytest

from backend import config
from backend.storage import db
from backend.storage.sqlite.schema import init_db

_TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def _truncate_postgres() -> None:
    with db.transaction() as conn:
        rows = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        ).fetchall()
        tables = [
            row["tablename"] for row in rows if row["tablename"] != "schema_migrations"
        ]
        if not tables:
            return
        quoted = ", ".join('"' + name.replace('"', '""') + '"' for name in tables)
        conn.execute(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE")


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Point settings at throwaway data storage and a fresh metadata schema."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setattr(config.settings, "ariadne_data_dir", str(data_root))
    if _TEST_DATABASE_URL:
        if (config.settings.database_url or "") != _TEST_DATABASE_URL:
            monkeypatch.setattr(config.settings, "database_url", _TEST_DATABASE_URL)
            db.reset_database_pool()
        init_db()
        _truncate_postgres()
    else:
        monkeypatch.setattr(config.settings, "database_url", None)
        monkeypatch.setattr(config.settings, "ariadne_db_path", str(tmp_path / "ariadne.db"))
        init_db()
    return tmp_path


def pytest_collection_modifyitems(items):
    if not _TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="SQLite-only migration test")
    for item in items:
        if "test_schema_v" in item.nodeid or "test_v18_database_migrates_to_v19" in item.nodeid:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    db.reset_database_pool()
