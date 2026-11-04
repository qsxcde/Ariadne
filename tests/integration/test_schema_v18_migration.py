"""v17 -> v18 records the embedder fingerprint on index snapshots."""

import pytest

from backend.storage.sqlite.connection import connect
from backend.storage.sqlite.schema import CURRENT_SCHEMA_VERSION, init_db


@pytest.mark.integration
def test_v18_migration_adds_snapshot_embedding_columns():
    with connect() as conn:
        conn.execute("PRAGMA user_version = 17")

    init_db()

    with connect() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(index_snapshots)")
        }
    assert version == CURRENT_SCHEMA_VERSION
    assert {"embedding_fingerprint", "embedding_model"} <= columns
