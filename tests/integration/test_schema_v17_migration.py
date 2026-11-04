"""v16 -> v17 adds per-user model settings without touching existing tables."""

import pytest

from backend.storage.sqlite.connection import connect
from backend.storage.sqlite.schema import CURRENT_SCHEMA_VERSION, init_db


@pytest.mark.integration
def test_v17_migration_creates_user_model_settings():
    with connect() as conn:
        conn.execute("PRAGMA user_version = 16")

    init_db()

    with connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(user_model_settings)")
        }
    assert version == CURRENT_SCHEMA_VERSION
    assert {"user_id", "llm_provider", "llm_model", "llm_api_key", "embedding_model",
            "rerank_model"} <= columns
