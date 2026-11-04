"""Copy a SQLite database into PostgreSQL.

The target schema is created (or upgraded) through the normal ``init_db`` path.
All writes happen in a single PostgreSQL transaction, so a failed run rolls back
an optional ``TRUNCATE`` together with every imported row.

Usage::

    uv run --project backend python -m backend.scripts.migrate_sqlite_to_postgres \
        --sqlite-path backend/data/ariadne.db \
        --database-url postgresql://ariadne:ariadne_dev@127.0.0.1:5432/ariadne \
        --dry-run

    # Re-run after a successful migration; this replaces the target contents.
    ... --truncate

The source must already be at the current schema version; start the application
once against it (or run the SQLite migrations) before migrating.
"""

import argparse
import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Any, Iterator

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from backend import config
from backend.storage import db
from backend.storage.sqlite.schema import CURRENT_SCHEMA_VERSION, init_db

TargetConnection = psycopg.Connection[dict[str, Any]]

# Parents before children: PostgreSQL enforces foreign keys per statement.
TABLE_ORDER = (
    "users",
    "papers",
    "collections",
    "sessions",
    "documents",
    "chunks",
    "retrieval_indexes",
    "jobs",
    "index_snapshots",
    "messages",
    "agent_runs",
    "agent_steps",
    "annotations",
    "collection_papers",
    "paper_tags",
    "subscriptions",
    "feed_items",
    "alert_settings",
    "user_model_settings",
    "notifications",
    "reading_log",
    "weekly_reports",
)

FOREIGN_KEYS = (
    ("sessions", "paper_id", "papers", "id"),
    ("documents", "paper_id", "papers", "id"),
    ("documents", "session_id", "sessions", "id"),
    ("chunks", "paper_id", "papers", "id"),
    ("chunks", "session_id", "sessions", "id"),
    ("chunks", "document_id", "documents", "id"),
    ("retrieval_indexes", "session_id", "sessions", "id"),
    ("jobs", "paper_id", "papers", "id"),
    ("jobs", "session_id", "sessions", "id"),
    ("jobs", "document_id", "documents", "id"),
    ("index_snapshots", "session_id", "sessions", "id"),
    ("messages", "session_id", "sessions", "id"),
    ("agent_runs", "session_id", "sessions", "id"),
    ("agent_steps", "run_id", "agent_runs", "id"),
    ("annotations", "paper_id", "papers", "id"),
    ("annotations", "document_id", "documents", "id"),
    ("annotations", "chunk_id", "chunks", "id"),
    ("collection_papers", "collection_id", "collections", "id"),
    ("collection_papers", "paper_id", "papers", "id"),
    ("paper_tags", "paper_id", "papers", "id"),
    ("feed_items", "paper_id", "papers", "id"),
)


class MigrationError(RuntimeError):
    """Raised when the source or target cannot be migrated safely."""


def run_migration(
    *,
    sqlite_path: Path,
    database_url: str,
    dry_run: bool = False,
    truncate: bool = False,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Copy every application table from SQLite into PostgreSQL."""
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if not sqlite_path.is_file():
        raise MigrationError(f"SQLite database not found: {sqlite_path}")

    _prepare_target(database_url)

    source = sqlite3.connect(str(sqlite_path))
    source.row_factory = sqlite3.Row
    source.execute("PRAGMA query_only = ON")
    try:
        source_version = int(source.execute("PRAGMA user_version").fetchone()[0])
        if source_version != CURRENT_SCHEMA_VERSION:
            raise MigrationError(
                f"Source schema version is {source_version}, expected "
                f"{CURRENT_SCHEMA_VERSION}. Start the application once against "
                f"the SQLite database to apply migrations."
            )
        _ensure_source_tables(source)
        source_orphans = _source_orphans(source)
        if source_orphans:
            details = ", ".join(
                f"{key}={value}" for key, value in source_orphans.items()
            )
            raise MigrationError(
                f"Source SQLite violates foreign keys ({details}); repair the "
                "source before migrating."
            )

        with psycopg.connect(database_url, row_factory=dict_row) as target:
            counts = _target_counts(target)
            populated = {table: count for table, count in counts.items() if count}
            if populated and not truncate and not dry_run:
                total = sum(populated.values())
                raise MigrationError(
                    f"Target already contains {total} rows across "
                    f"{len(populated)} tables; pass --truncate to replace it."
                )

            report: dict[str, Any] = {
                "dry_run": dry_run,
                "truncate": truncate,
                "source": str(sqlite_path),
                "tables": {},
                "checksums_ok": True,
                "target_orphans": {},
            }

            if dry_run:
                for table in TABLE_ORDER:
                    source_count = _source_count(source, table)
                    report["tables"][table] = {
                        "source": source_count,
                        "target_before": counts[table],
                        "target_after": counts[table],
                    }
                return report

            if truncate:
                target.execute(
                    sql.SQL("TRUNCATE TABLE {} CASCADE").format(
                        sql.SQL(", ").join(
                            sql.Identifier(table) for table in TABLE_ORDER
                        )
                    )
                )

            source_digests: dict[str, str] = {}
            for table in TABLE_ORDER:
                columns = _common_columns(source, target, table)
                insert_sql = sql.SQL(
                    "INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING"
                ).format(
                    sql.Identifier(table),
                    sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                    sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                )
                source_count, digest = _copy_table(
                    source,
                    target,
                    table,
                    columns,
                    insert_sql,
                    batch_size,
                )
                source_digests[table] = digest
                report["tables"][table] = {
                    "source": source_count,
                    "target_before": counts[table],
                    "target_after": _target_count(target, table),
                }

            mismatched = [
                table
                for table, stats in report["tables"].items()
                if stats["source"] != stats["target_after"]
            ]
            if mismatched:
                details = ", ".join(
                    f"{table} ({report['tables'][table]['source']} -> "
                    f"{report['tables'][table]['target_after']})"
                    for table in mismatched
                )
                raise MigrationError(f"Row count mismatch after import: {details}")

            for table in TABLE_ORDER:
                columns = _common_columns(source, target, table)
                target_digest = _target_digest(target, table, columns)
                if target_digest != source_digests[table]:
                    report["checksums_ok"] = False
                    raise MigrationError(
                        f"Checksum mismatch for {table}; imported rows differ "
                        "from the source."
                    )

            report["target_orphans"] = _target_orphans(target)
            if any(report["target_orphans"].values()):
                details = ", ".join(
                    f"{key}={value}"
                    for key, value in report["target_orphans"].items()
                    if value
                )
                raise MigrationError(
                    f"Imported data violates foreign keys ({details})."
                )

            target.commit()
            return report
    finally:
        source.close()


def _prepare_target(database_url: str) -> None:
    if database_url.startswith("sqlite"):
        raise MigrationError("--database-url must point to PostgreSQL")
    config.settings.database_url = database_url
    db.reset_database_pool()
    init_db()


def _ensure_source_tables(source: sqlite3.Connection) -> None:
    existing = {
        str(row["name"])
        for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = [table for table in TABLE_ORDER if table not in existing]
    if missing:
        raise MigrationError(
            f"Source SQLite is missing tables: {', '.join(missing)}"
        )


def _source_columns(source: sqlite3.Connection, table: str) -> list[str]:
    rows = source.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [str(row["name"]) for row in rows]


def _target_columns(target: TargetConnection, table: str) -> list[str]:
    rows = target.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return [str(row["column_name"]) for row in rows]


def _common_columns(
    source: sqlite3.Connection,
    target: TargetConnection,
    table: str,
) -> list[str]:
    source_columns = _source_columns(source, table)
    target_columns = _target_columns(target, table)
    if not target_columns:
        raise MigrationError(
            f"Target table {table} does not exist; PostgreSQL schema "
            "initialization failed."
        )
    missing = [column for column in target_columns if column not in source_columns]
    if missing:
        raise MigrationError(
            f"Source table {table} is missing columns required by PostgreSQL: "
            f"{', '.join(missing)}. Start the application once against the "
            "SQLite database to apply migrations."
        )
    return target_columns


def _source_count(source: sqlite3.Connection, table: str) -> int:
    row = source.execute(f'SELECT COUNT(*) AS total FROM "{table}"').fetchone()
    return int(row["total"])


def _target_count(target: TargetConnection, table: str) -> int:
    row = target.execute(
        sql.SQL("SELECT COUNT(*) AS total FROM {}").format(sql.Identifier(table))
    ).fetchone()
    assert row is not None
    return int(row["total"])


def _target_counts(target: TargetConnection) -> dict[str, int]:
    return {table: _target_count(target, table) for table in TABLE_ORDER}


def _batches(
    cursor: sqlite3.Cursor, batch_size: int
) -> Iterator[list[tuple[Any, ...]]]:
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            return
        yield [tuple(row) for row in rows]


def _copy_table(
    source: sqlite3.Connection,
    target: TargetConnection,
    table: str,
    columns: list[str],
    insert_sql: sql.Composed,
    batch_size: int,
) -> tuple[int, str]:
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    select_sql = f'SELECT {quoted_columns} FROM "{table}"'
    cursor = source.execute(select_sql)
    digests: list[bytes] = []
    total = 0
    with target.cursor() as target_cursor:
        for batch in _batches(cursor, batch_size):
            digests.extend(_row_digest(row) for row in batch)
            target_cursor.executemany(insert_sql, batch)
            total += len(batch)
    return total, _combine_digests(digests)


def _target_digest(
    target: TargetConnection,
    table: str,
    columns: list[str],
) -> str:
    select_sql = sql.SQL("SELECT {} FROM {}").format(
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.Identifier(table),
    )
    rows = target.execute(select_sql).fetchall()
    return _combine_digests(
        _row_digest(tuple(row[column] for column in columns)) for row in rows
    )


def _row_digest(row: tuple[Any, ...]) -> bytes:
    return hashlib.sha256(repr(row).encode("utf-8")).digest()


def _combine_digests(digests: Iterator[bytes] | list[bytes]) -> str:
    ordered = sorted(digests)
    digest = hashlib.sha256()
    for item in ordered:
        digest.update(item)
    return digest.hexdigest()


def _source_orphans(source: sqlite3.Connection) -> dict[str, int]:
    result: dict[str, int] = {}
    for table, column, ref_table, ref_column in FOREIGN_KEYS:
        row = source.execute(
            f'SELECT COUNT(*) AS total FROM "{table}" t '
            f'WHERE t."{column}" IS NOT NULL AND NOT EXISTS ('
            f'SELECT 1 FROM "{ref_table}" r WHERE r."{ref_column}" = t."{column}")'
        ).fetchone()
        count = int(row["total"])
        if count:
            result[f"{table}.{column}"] = count
    return result


def _target_orphans(target: TargetConnection) -> dict[str, int]:
    result: dict[str, int] = {}
    for table, column, ref_table, ref_column in FOREIGN_KEYS:
        row = target.execute(
            sql.SQL(
                "SELECT COUNT(*) AS total FROM {table} t "
                "WHERE t.{column} IS NOT NULL AND NOT EXISTS ("
                "SELECT 1 FROM {ref_table} r WHERE r.{ref_column} = t.{column})"
            ).format(
                table=sql.Identifier(table),
                column=sql.Identifier(column),
                ref_table=sql.Identifier(ref_table),
                ref_column=sql.Identifier(ref_column),
            )
        ).fetchone()
        assert row is not None
        count = int(row["total"])
        if count:
            result[f"{table}.{column}"] = count
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy a SQLite database into PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="source database (default: <data dir>/ariadne.db)",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="target PostgreSQL URL (default: $DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report row counts without writing",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="replace existing target rows (rolled back on failure)",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url or DATABASE_URL is required")
    sqlite_path = args.sqlite_path or db.get_db_path()

    report = run_migration(
        sqlite_path=sqlite_path,
        database_url=args.database_url,
        dry_run=args.dry_run,
        truncate=args.truncate,
        batch_size=args.batch_size,
    )

    mode = "dry-run" if args.dry_run else "migrated"
    print(f"[{mode}] source={report['source']}")
    for table in TABLE_ORDER:
        stats = report["tables"][table]
        print(
            f"  {table:24} source={stats['source']:>8} "
            f"target={stats['target_after']:>8}"
        )
    if args.dry_run:
        print("No rows were written. Re-run without --dry-run to migrate.")
    else:
        print("Row counts, checksums and foreign keys verified.")


if __name__ == "__main__":
    main()
