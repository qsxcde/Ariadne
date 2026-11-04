"""BibTeX / CSL JSON / Markdown export for the personal library."""

import io
import json
from collections.abc import Mapping
from typing import Any

from pybtex.database import BibliographyData, Entry
from pybtex.database.output.bibtex import Writer

from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import papers as paper_repo

# Fields copied verbatim from the persisted paper row, in BibTeX naming.
_BIBTEX_TEXT_FIELDS = (
    ("journal", "venue"),
    ("doi", "doi"),
    ("url", "url"),
    ("abstract", "abstract"),
)


def _authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _bibtex_entry(paper: Mapping[str, Any]) -> Entry:
    """Map a paper row to a pybtex entry (escaping and joining are delegated)."""
    fields: dict[str, str] = {"title": str(paper["title"])}
    authors = _authors(paper["authors_json"])
    if authors:
        # pybtex writes ``author`` verbatim, so ordering survives unchanged.
        fields["author"] = " and ".join(authors)
    if paper["year"]:
        fields["year"] = str(paper["year"])
    for bibtex_name, column in _BIBTEX_TEXT_FIELDS:
        value = paper[column]
        if value:
            fields[bibtex_name] = str(value)
    return Entry("article", fields=fields)


def export_bibtex(user_id: str | None) -> str:
    papers = paper_repo.list_papers(user_id, limit=1000)
    if not papers:
        return ""
    bibliography = BibliographyData()
    for paper in papers:
        bibliography.add_entry(str(paper["id"]), _bibtex_entry(paper))
    stream = io.StringIO()
    Writer().write_stream(bibliography, stream)
    return stream.getvalue().replace("\r\n", "\n").strip() + "\n"


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
    lines = ["# Ariadne Library", ""]
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
