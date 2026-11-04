"""Detect new arXiv versions for tracked papers and emit notifications."""

from typing import Any

from backend.application.follow import notifications as notification_service
from backend.application.library.paper_import import fetch_arxiv_updated
from backend.storage.sqlite import alerts as alert_repo
from backend.storage.sqlite import papers as paper_repo


def check_version_updates(user_id: str | None) -> dict[str, Any]:
    """Compare each paper's arXiv updated timestamp with the last snapshot.

    The first run only records a baseline; later runs notify when arXiv reports a
    newer version. Papers without an arXiv id are skipped.
    """
    preferences = alert_repo.get_or_create(user_id)
    papers = [
        paper for paper in paper_repo.list_papers(user_id, limit=1000) if paper["arxiv_id"]
    ]
    checked = updated = notified = 0
    errors: list[str] = []

    for paper in papers:
        try:
            latest = fetch_arxiv_updated(str(paper["arxiv_id"]))
        except Exception as exc:  # 网络/解析失败：降级并继续
            errors.append(f"{paper['title']}: {exc}")
            continue
        if not latest:
            errors.append(f"{paper['title']}: arXiv 未返回更新时间")
            continue
        checked += 1
        previous = paper.get("last_arxiv_updated")
        if (
            previous
            and latest > str(previous)
            and int(preferences["new_version"])
        ):
            notification_service.create_notification(
                user_id,
                kind="version",
                title=f"《{paper['title']}》有新版本",
                body=f"arXiv 更新时间 {previous} → {latest}。",
            )
            notified += 1
        if previous != latest:
            paper_repo.update_arxiv_updated(paper["id"], latest)
            updated += 1

    return {
        "checked": checked,
        "updated": updated,
        "notified": notified,
        "errors": errors,
    }
