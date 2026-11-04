"""Database access facade: SQLite by default, PostgreSQL when configured."""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from backend import config

_pg_pool: Any | None = None
_pg_pool_lock = threading.Lock()


def get_db_path() -> Path:
    """Resolve the SQLite file used when DATABASE_URL is empty."""
    if config.settings.ariadne_db_path:
        return Path(config.settings.ariadne_db_path).expanduser()
    return config.data_dir() / "ariadne.db"


def database_url() -> str:
    return (config.settings.database_url or "").strip()


def is_postgres() -> bool:
    url = database_url().lower()
    return url.startswith("postgresql://") or url.startswith("postgres://")


def _translate_sql(sql: str) -> str:
    """Translate the SQLite dialect used by repositories to PostgreSQL.

    Repository SQL uses qmark placeholders and SQLite's ``IS ?`` null-safe
    comparison. Everything else stays standard SQL.
    """
    out: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if in_single:
            out.append(char)
            if char == "'":
                if index + 1 < len(sql) and sql[index + 1] == "'":
                    out.append(sql[index + 1])
                    index += 2
                    continue
                in_single = False
            index += 1
            continue
        if in_double:
            out.append(char)
            if char == '"':
                if index + 1 < len(sql) and sql[index + 1] == '"':
                    out.append(sql[index + 1])
                    index += 2
                    continue
                in_double = False
            index += 1
            continue
        if char == "'":
            in_single = True
            out.append(char)
            index += 1
            continue
        if char == '"':
            in_double = True
            out.append(char)
            index += 1
            continue
        if char == "?":
            text = "".join(out)
            stripped = text.rstrip()
            starts_word = len(stripped) < 3 or not (
                stripped[-3].isalnum() or stripped[-3] == "_"
            )
            if stripped[-2:].upper() == "IS" and starts_word:
                out = [stripped[:-2], "IS NOT DISTINCT FROM %s"]
            else:
                out.append("%s")
            index += 1
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _split_sql(script: str) -> list[str]:
    """Split a DDL script on semicolons outside quoted strings."""
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(script):
        char = script[index]
        if in_single:
            current.append(char)
            if char == "'":
                if index + 1 < len(script) and script[index + 1] == "'":
                    current.append(script[index + 1])
                    index += 2
                    continue
                in_single = False
            index += 1
            continue
        if in_double:
            current.append(char)
            if char == '"':
                if index + 1 < len(script) and script[index + 1] == '"':
                    current.append(script[index + 1])
                    index += 2
                    continue
                in_double = False
            index += 1
            continue
        if char == "'":
            in_single = True
            current.append(char)
        elif char == '"':
            in_double = True
            current.append(char)
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


class PostgresConnection:
    """Small DB-API facade so repositories keep their existing call shape."""

    def __init__(self, pool: Any, conn: Any) -> None:
        self._pool = pool
        self._conn = conn
        self._closed = False

    def execute(self, sql: str, params: tuple | dict | None = None) -> Any:
        translated = _translate_sql(sql)
        if params is None:
            return self._conn.execute(translated)
        return self._conn.execute(translated, params)

    def executemany(self, sql: str, params: list[tuple]) -> Any:
        with self._conn.cursor() as cursor:
            return cursor.executemany(_translate_sql(sql), params)

    def executescript(self, script: str) -> None:
        for statement in _split_sql(script):
            self.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._pool.putconn(self._conn)

    def __enter__(self) -> "PostgresConnection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self.close()


def _get_pool() -> Any:
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            return _pg_pool
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        min_size = max(1, config.settings.db_pool_min_size)
        max_size = max(min_size, config.settings.db_pool_max_size)
        _pg_pool = ConnectionPool(
            conninfo=database_url(),
            min_size=min_size,
            max_size=max_size,
            timeout=config.settings.db_connect_timeout,
            kwargs={"row_factory": dict_row},
            open=True,
            name="ariadne-db",
        )
        _pg_pool.wait(timeout=config.settings.db_connect_timeout)
        return _pg_pool


def reset_database_pool() -> None:
    """Close the pool after configuration changes (tests, process shutdown)."""
    global _pg_pool
    with _pg_pool_lock:
        if _pg_pool is not None:
            _pg_pool.close()
            _pg_pool = None


def _sqlite_connect() -> sqlite3.Connection:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -8000")
    conn.execute("PRAGMA mmap_size = 268435456")
    return conn


def connect() -> Any:
    if is_postgres():
        pool = _get_pool()
        return PostgresConnection(pool, pool.getconn())
    return _sqlite_connect()


@contextmanager
def transaction() -> Iterator[Any]:
    if is_postgres():
        pool = _get_pool()
        conn: Any = PostgresConnection(pool, pool.getconn())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return
    conn = _sqlite_connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: Any | None) -> dict | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)
