"""PostgreSQL backend smoke tests; run with TEST_DATABASE_URL set."""

import os

import pytest

from backend.storage import db
from backend.storage.sqlite import model_settings, papers
from backend.storage.sqlite.schema import CURRENT_SCHEMA_VERSION

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured",
)


@pytest.mark.integration
def test_pg_schema_version_and_null_safe_queries() -> None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT MAX(version) AS version FROM schema_migrations"
        ).fetchone()

    assert row is not None
    assert row["version"] == CURRENT_SCHEMA_VERSION


@pytest.mark.integration
def test_postgres_queries_match_sqlite_semantics() -> None:
    paper = papers.create_paper(
        user_id="pg-user",
        title="Attention Is All You Need",
        doi="10.1000/ABC",
    )

    assert papers.find_by_doi("pg-user", "10.1000/abc")["id"] == paper["id"]
    assert [item["id"] for item in papers.list_papers("pg-user", query="attention")] == [
        paper["id"]
    ]

    first = model_settings.get_or_create(None)
    second = model_settings.get_or_create(None)
    assert first["id"] == second["id"]
