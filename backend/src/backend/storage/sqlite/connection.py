"""Backward-compatible import site for database access.

The implementation lives in :mod:`backend.storage.db` and dispatches to SQLite
or PostgreSQL based on ``DATABASE_URL``.
"""

from backend.storage.db import (
    connect,
    get_db_path,
    is_postgres,
    reset_database_pool,
    row_to_dict,
    transaction,
)

__all__ = [
    "connect",
    "get_db_path",
    "is_postgres",
    "reset_database_pool",
    "row_to_dict",
    "transaction",
]
