"""Reading-time use cases."""

from typing import Any

from backend.application.library.papers import get_accessible_paper
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import reading as reading_repo

MAX_SECONDS_PER_REPORT = 3600


def record_reading_time(
    paper_id: str, user_id: str | None, seconds: int
) -> dict[str, Any]:
    """Record active reading seconds; reject papers the caller cannot access."""
    get_accessible_paper(paper_id, user_id)
    added = reading_repo.record_reading(
        user_id, paper_id, min(max(int(seconds), 1), MAX_SECONDS_PER_REPORT)
    )
    paper = paper_repo.get_paper(paper_id)
    return {
        "paper_id": paper_id,
        "added_seconds": added,
        "total_seconds": int(paper["time_spent_seconds"]) if paper else 0,
    }


def reading_stats(user_id: str | None, days: int = 7) -> dict[str, Any]:
    return reading_repo.summarize(user_id, days)
