"""BibTeX / CSL JSON / Markdown export for the personal library."""

import json
from collections.abc import Mapping
from typing import Any

from backend.storage.sqlite import annotations as annotation_repo
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


def export_csl_json(user_id: str | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for paper in paper_repo.list_papers(user_id, limit=1000):
        authors = []
        for name in _authors(paper["authors_json"]):
            parts = name.split()
            authors.append(
                {
                    "family": parts[-1] if parts else name,
                    "given": " ".join(parts[:-1]),
                }
            )
        item: dict[str, Any] = {
            "id": paper["id"],
            "type": "article-journal",
            "title": paper["title"],
            "author": authors,
            "abstract": paper["abstract"] or "",
        }
        if paper["year"]:
            item["issued"] = {"date-parts": [[paper["year"]]]}
        if paper["venue"]:
            item["container-title"] = paper["venue"]
        if paper["doi"]:
            item["DOI"] = paper["doi"]
        if paper["url"]:
            item["URL"] = paper["url"]
        result.append(item)
    return result


def export_markdown(user_id: str | None) -> str:
    papers = paper_repo.list_papers(user_id, limit=1000)
    lines = ["# SciPal Library", ""]
    for paper in papers:
        lines.append(f"## {paper['title']}")
        authors = _authors(paper["authors_json"])
        if authors:
            lines.append(f"- Authors: {', '.join(authors)}")
        if paper["year"]:
            lines.append(f"- Year: {paper['year']}")
        if paper["venue"]:
            lines.append(f"- Venue: {paper['venue']}")
        if paper["doi"]:
            lines.append(f"- DOI: {paper['doi']}")
        lines.append(f"- Status: {paper['reading_status']}")
        lines.append(f"- Progress: {round(float(paper['progress']) * 100)}%")
        annotations = annotation_repo.list_annotations(paper["id"])
        if annotations:
            lines.append("- Notes:")
            for annotation in annotations:
                quote = f"> {annotation['quote']}\n" if annotation["quote"] else ""
                content = annotation["content"] or ""
                lines.append(f"  - {quote}{content}".strip())
        lines.append("")
    return "\n".join(lines)
