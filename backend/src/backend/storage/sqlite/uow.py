"""Explicit transaction boundary for multi-step storage work."""

from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3

from backend.storage.sqlite.connection import transaction


@contextmanager
def unit_of_work() -> Iterator[sqlite3.Connection]:
    """Run a block in one transaction; commit on success, roll back on error."""
    with transaction() as conn:
        yield conn
