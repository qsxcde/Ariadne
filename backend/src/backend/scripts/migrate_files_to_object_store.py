"""Copy locally stored artifacts into the object store and rewrite references.

Run it once when switching an existing deployment from ``local`` to ``s3``:
uploads, parsed artifacts, crops and index snapshots are uploaded under keys
relative to the data directory, then the columns that held absolute paths are
updated. Re-running is a no-op because references already stored as keys are
skipped.

Usage::

    # environment: OBJECT_STORE_BACKEND=s3 plus OBJECT_STORE_* settings
    uv run --project backend python -m backend.scripts.migrate_files_to_object_store
    uv run --project backend python -m backend.scripts.migrate_files_to_object_store \
        --apply [--delete-local]

Without ``--apply`` nothing is uploaded or written. ``--delete-local`` removes
files only after the database transaction commits.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from backend import config
from backend.storage import db
from backend.storage.db import connect, transaction
from backend.storage.object_store import get_object_store

REFERENCE_FIELDS = (
    (
        "documents",
        "id",
        (
            "file_path",
            "parsed_ir_path",
            "parsed_markdown_path",
            "quality_report_path",
        ),
    ),
    ("index_snapshots", "id", ("index_path", "chunks_path")),
    ("retrieval_indexes", "id", ("index_path", "chunks_path")),
)


@dataclass(frozen=True)
class Upload:
    source: Path
    key: str


@dataclass(frozen=True)
class ReferenceUpdate:
    table: str
    id_column: str
    row_id: str
    field: str
    original: str
    key: str


def build_plan() -> tuple[list[Upload], list[ReferenceUpdate], list[str]]:
    store = get_object_store()
    if store.backend != "s3":
        raise RuntimeError(
            "Object store backend is 'local'; set OBJECT_STORE_BACKEND=s3 "
            "before migrating files."
        )
    root = config.data_dir().resolve()
    uploads: dict[Path, Upload] = {}
    updates: list[ReferenceUpdate] = []
    skipped: list[str] = []

    for table, id_column, fields in REFERENCE_FIELDS:
        for row in _select(table, id_column, fields):
            for field in fields:
                raw = row.get(field)
                if not raw:
                    continue
                source = Path(str(raw))
                if not source.is_absolute():
                    continue
                resolved = source.resolve()
                if not resolved.is_relative_to(root):
                    skipped.append(f"{table}.{field} outside data dir: {raw}")
                    continue
                if not resolved.is_file():
                    skipped.append(f"{table}.{field} missing: {raw}")
                    continue
                key = resolved.relative_to(root).as_posix()
                uploads.setdefault(resolved, Upload(resolved, key))
                updates.append(
                    ReferenceUpdate(
                        table=table,
                        id_column=id_column,
                        row_id=str(row[id_column]),
                        field=field,
                        original=str(raw),
                        key=key,
                    )
                )
                if field == "parsed_ir_path":
                    for child in resolved.parent.rglob("*"):
                        if child.is_file():
                            child_resolved = child.resolve()
                            uploads.setdefault(
                                child_resolved,
                                Upload(
                                    child_resolved,
                                    child_resolved.relative_to(root).as_posix(),
                                ),
                            )
    return list(uploads.values()), updates, skipped


def run(*, apply: bool, delete_local: bool = False) -> dict:
    uploads, updates, skipped = build_plan()
    total_bytes = sum(item.source.stat().st_size for item in uploads)
    if not apply:
        return {
            "uploads": len(uploads),
            "updates": len(updates),
            "bytes": total_bytes,
            "skipped": skipped,
            "applied": False,
        }

    store = get_object_store()
    for item in uploads:
        store.put_file(item.key, item.source)

    with transaction() as conn:
        for update in updates:
            conn.execute(
                f'UPDATE "{update.table}" '
                f'SET "{update.field}" = ? '
                f'WHERE "{update.id_column}" = ? AND "{update.field}" = ?',
                (update.key, update.row_id, update.original),
            )

    if delete_local:
        for item in uploads:
            item.source.unlink(missing_ok=True)
            _prune_empty_dirs(item.source.parent)

    return {
        "uploads": len(uploads),
        "updates": len(updates),
        "bytes": total_bytes,
        "skipped": skipped,
        "applied": True,
    }


def _select(table: str, id_column: str, fields: tuple[str, ...]) -> list[dict]:
    columns = ", ".join((id_column, *fields))
    with connect() as conn:
        rows = conn.execute(f'SELECT {columns} FROM "{table}"').fetchall()
    return [dict(row) for row in rows]


def _prune_empty_dirs(start: Path) -> None:
    root = config.data_dir().resolve()
    current = start.resolve()
    while current != root and current.is_relative_to(root):
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload local artifacts to the object store and rewrite references"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="upload files and update the database (default: dry run)",
    )
    parser.add_argument(
        "--delete-local",
        action="store_true",
        help="delete local files after a successful commit",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="override DATABASE_URL for this run",
    )
    args = parser.parse_args()
    if args.delete_local and not args.apply:
        parser.error("--delete-local requires --apply")
    if args.database_url:
        config.settings.database_url = args.database_url
        db.reset_database_pool()

    report = run(apply=args.apply, delete_local=args.delete_local)
    mode = "applied" if report["applied"] else "dry-run"
    print(
        f"[{mode}] uploads={report['uploads']} updates={report['updates']} "
        f"bytes={report['bytes']} skipped={len(report['skipped'])}"
    )
    for item in report["skipped"]:
        print(f"  skipped: {item}")
    if not report["applied"]:
        print("No files uploaded or rows updated. Re-run with --apply.")


if __name__ == "__main__":
    main()
