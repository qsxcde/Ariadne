"""Report and merge duplicate papers that share a user + file hash."""

import argparse

from backend.storage.sqlite.connection import connect, transaction


def find_duplicate_groups() -> list[dict[str, object]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.user_id, d.file_hash,
                   GROUP_CONCAT(DISTINCT p.id) AS paper_ids
            FROM documents d
            JOIN papers p ON p.id = d.paper_id
            WHERE d.file_hash IS NOT NULL
            GROUP BY p.user_id, d.file_hash
            HAVING COUNT(DISTINCT p.id) > 1
            ORDER BY MIN(p.created_at) ASC
            """
        ).fetchall()
    return [
        {
            "user_id": row["user_id"],
            "file_hash": row["file_hash"],
            "paper_ids": str(row["paper_ids"]).split(","),
        }
        for row in rows
    ]


def merge_group(keeper_id: str, duplicate_ids: list[str]) -> None:
    if not duplicate_ids:
        return
    placeholders = ", ".join("?" for _ in duplicate_ids)
    params: tuple[object, ...] = (keeper_id, *duplicate_ids)
    with transaction() as conn:
        conn.execute(
            f"UPDATE documents SET paper_id = ? WHERE paper_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"UPDATE chunks SET paper_id = ? WHERE paper_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"UPDATE jobs SET paper_id = ? WHERE paper_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"UPDATE sessions SET paper_id = ? WHERE paper_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"UPDATE annotations SET paper_id = ? WHERE paper_id IN ({placeholders})",
            params,
        )
        conn.execute(
            f"""
            INSERT OR IGNORE INTO collection_papers (
              collection_id, paper_id, added_at, sort_order
            )
            SELECT collection_id, ?, added_at, sort_order
            FROM collection_papers
            WHERE paper_id IN ({placeholders})
            """,
            params,
        )
        conn.execute(
            f"DELETE FROM collection_papers WHERE paper_id IN ({placeholders})",
            (*duplicate_ids,),
        )
        conn.execute(
            f"""
            INSERT OR IGNORE INTO paper_tags (paper_id, tag)
            SELECT ?, tag FROM paper_tags WHERE paper_id IN ({placeholders})
            """,
            params,
        )
        conn.execute(
            f"DELETE FROM paper_tags WHERE paper_id IN ({placeholders})",
            (*duplicate_ids,),
        )
        conn.execute(
            f"DELETE FROM papers WHERE id IN ({placeholders})",
            (*duplicate_ids,),
        )


def run(*, apply: bool) -> dict[str, int]:
    groups = find_duplicate_groups()
    merged = 0
    for group in groups:
        paper_ids = list(group["paper_ids"])  # type: ignore[arg-type]
        if len(paper_ids) < 2:
            continue
        if apply:
            merge_group(paper_ids[0], paper_ids[1:])
        merged += len(paper_ids) - 1
    return {"groups": len(groups), "papers": merged}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="merge duplicates")
    args = parser.parse_args()
    result = run(apply=args.apply)
    mode = "merged" if args.apply else "would merge"
    print(f"{mode}: {result['papers']} papers in {result['groups']} groups")


if __name__ == "__main__":
    main()
