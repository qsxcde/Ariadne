"""Detect new citations for tracked papers and emit notifications."""

from typing import Any

from backend.application import notifications as notification_service
from backend.application.citations import get_citation_graph
from backend.storage.sqlite import alerts as alert_repo
from backend.storage.sqlite import papers as paper_repo


def check_citation_updates(user_id: str | None) -> dict[str, Any]:
    """Compare each paper's OpenAlex citation count with the last snapshot.

    The first run only records a baseline; later runs notify when the count grows.
    Unindexed papers are reported in ``errors`` instead of aborting the batch.
    """
    preferences = alert_repo.get_or_create(user_id)
    papers = paper_repo.list_papers(user_id, limit=1000)
    checked = updated = notified = 0
    errors: list[str] = []

    for paper in papers:
        try:
            graph = get_citation_graph(paper["id"], user_id)
        except Exception as exc:  # 数据源未收录或网络失败：降级并继续
            errors.append(f"{paper['title']}: {exc}")
            continue
        checked += 1
        current = int(graph.get("cited_by_count") or 0)
        previous = paper.get("last_citation_count")
        if (
            previous is not None
            and current > int(previous)
            and int(preferences["new_citation"])
        ):
            notification_service.create_notification(
                user_id,
                kind="citation",
                title=f"《{paper['title']}》新增引用",
                body=f"被引次数 {previous} → {current}。",
            )
            notified += 1
        if previous is None or current != int(previous):
            paper_repo.update_citation_count(paper["id"], current)
            updated += 1

    return {
        "checked": checked,
        "updated": updated,
        "notified": notified,
        "errors": errors,
    }
