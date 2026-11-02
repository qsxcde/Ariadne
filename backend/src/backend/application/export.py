"""BibTeX export for the personal library."""

import json
from collections.abc import Mapping
from typing import Any

from backend.storage.sqlite import papers as paper_repo


def _authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _entry(paper: Mapping[str, Any]) -> str:
    fields: list[tuple[str, str]] = [
        ("title", paper["title"]),
        ("author", " and ".join(_authors(paper["authors_json"]))),
        ("year", str(paper["year"]) if paper["year"] else ""),
        ("journal", paper["venue"] or ""),
        ("doi", paper["doi"] or ""),
        ("url", paper["url"] or ""),
        ("abstract", paper["abstract"] or ""),
    ]
    body = "\n".join(
        f"  {name} = {{{value}}}," for name, value in fields if value
    )
    return f"@article{{{paper['id']},\n{body}\n}}"


def export_bibtex(user_id: str | None) -> str:
    papers = paper_repo.list_papers(user_id, limit=1000)
    return "\n\n".join(_entry(paper) for paper in papers) + ("\n" if papers else "")
