"""Token-based Zotero / Notion export.

OAuth is intentionally not required for the personal single-user version:
the user supplies a Zotero API key or Notion integration token per request.
"""

import json
from collections.abc import Mapping
from typing import Any

import httpx

from backend.storage.sqlite import papers as paper_repo


def _authors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _zotero_item(paper: Mapping[str, Any]) -> dict[str, Any]:
    creators = []
    for name in _authors(paper["authors_json"]):
        parts = name.split()
        creators.append(
            {
                "creatorType": "author",
                "firstName": " ".join(parts[:-1]),
                "lastName": parts[-1] if parts else name,
            }
        )
    item = {
        "itemType": "journalArticle",
        "title": paper["title"],
        "creators": creators,
        "abstractNote": paper["abstract"] or "",
        "url": paper["url"] or "",
        "DOI": paper["doi"] or "",
        "publicationTitle": paper["venue"] or "",
    }
    if paper["year"]:
        item["date"] = str(paper["year"])
    return item


def export_to_zotero(
    user_id: str | None,
    *,
    api_key: str,
    library_id: str,
    library_type: str = "user",
    client: Any | None = None,
) -> dict[str, int]:
    papers = paper_repo.list_papers(user_id, limit=1000)
    if not papers:
        return {"exported": 0}
    prefix = "users" if library_type == "user" else "groups"
    url = f"https://api.zotero.org/{prefix}/{library_id}/items"
    http = client or httpx
    response = http.post(
        url,
        headers={
            "Zotero-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json=[_zotero_item(paper) for paper in papers],
        timeout=30,
    )
    response.raise_for_status()
    return {"exported": len(papers)}


def export_to_notion(
    user_id: str | None,
    *,
    token: str,
    database_id: str,
    client: Any | None = None,
) -> dict[str, int]:
    papers = paper_repo.list_papers(user_id, limit=1000)
    http = client or httpx
    exported = 0
    for paper in papers:
        properties: dict[str, Any] = {
            "Name": {"title": [{"text": {"content": paper["title"]}}]},
        }
        if paper["url"]:
            properties["URL"] = {"url": paper["url"]}
        if paper["doi"]:
            properties["DOI"] = {
                "rich_text": [{"text": {"content": paper["doi"]}}]
            }
        response = http.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "parent": {"database_id": database_id},
                "properties": properties,
            },
            timeout=30,
        )
        response.raise_for_status()
        exported += 1
    return {"exported": exported}
