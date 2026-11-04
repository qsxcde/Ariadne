"""Aggregate library dashboard statistics."""

from collections import Counter
from typing import Any

from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import feed as feed_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import reading as reading_repo


def library_stats(user_id: str | None) -> dict[str, Any]:
    papers = paper_repo.list_papers(user_id, limit=1000)
    statuses = Counter(paper["reading_status"] for paper in papers)
    paper_ids = [paper["id"] for paper in papers]
    counts = annotation_repo.count_by_type_for_papers(paper_ids)
    notes = counts.get("note", 0) + counts.get("highlight", 0)
    questions = counts.get("question", 0)
    reading = reading_repo.summarize(user_id)
    return {
        "total": len(papers),
        "by_status": {status: statuses.get(status, 0) for status in ("inbox", "queued", "skimming", "reading", "read", "archived")},
        "notes": notes,
        "questions": questions,
        "collections": len(collection_repo.list_collections(user_id)),
        "feed_saved": len(feed_repo.list_feed_items(user_id, status="saved")),
        "reading_seconds_today": reading["today_seconds"],
        "reading_seconds_week": reading["week_seconds"],
    }
