"""Aggregate library dashboard statistics."""

from collections import Counter
from typing import Any

from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import feed as feed_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite.connection import connect


def library_stats(user_id: str | None) -> dict[str, Any]:
    papers = paper_repo.list_papers(user_id, limit=1000)
    statuses = Counter(paper["reading_status"] for paper in papers)
    paper_ids = [paper["id"] for paper in papers]
    notes = 0
    questions = 0
    if paper_ids:
        placeholders = ", ".join("?" for _ in paper_ids)
        with connect() as conn:
            rows = conn.execute(
                f"SELECT type, COUNT(*) AS total FROM annotations WHERE paper_id IN ({placeholders}) GROUP BY type",
                tuple(paper_ids),
            ).fetchall()
        counts = {str(row["type"]): int(row["total"]) for row in rows}
        notes = counts.get("note", 0) + counts.get("highlight", 0)
        questions = counts.get("question", 0)
    return {
        "total": len(papers),
        "by_status": {status: statuses.get(status, 0) for status in ("inbox", "queued", "skimming", "reading", "read", "archived")},
        "notes": notes,
        "questions": questions,
        "collections": len(collection_repo.list_collections(user_id)),
        "feed_saved": len(feed_repo.list_feed_items(user_id, status="saved")),
    }
