"""Backfill SHA-256 hashes for documents imported before schema v8."""

import argparse
import hashlib
from pathlib import Path

from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite.connection import connect


def _iter_missing_hashes():
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, file_path FROM documents WHERE file_hash IS NULL"
        ).fetchall()
    for row in rows:
        yield str(row["id"]), str(row["file_path"])


def run(*, apply: bool) -> dict[str, int]:
    updated = 0
    missing = 0
    for document_id, file_path in _iter_missing_hashes():
        path = Path(file_path)
        if not path.is_file():
            missing += 1
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if apply:
            document_repo.update_document_file_hash(document_id, digest)
        updated += 1
    return {"updated": updated, "missing": missing}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write hashes to SQLite")
    args = parser.parse_args()
    result = run(apply=args.apply)
    mode = "updated" if args.apply else "would update"
    print(f"{mode}: {result['updated']}, missing files: {result['missing']}")


if __name__ == "__main__":
    main()
