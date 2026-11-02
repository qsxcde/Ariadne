"""OpenAlex citation graph for one paper."""

from collections.abc import Mapping
from typing import Any

import httpx

from backend.application.papers import get_accessible_paper

_BASE = "https://api.openalex.org/works"


def _work_url(paper: Mapping[str, Any]) -> str:
    if paper["doi"]:
        doi = str(paper["doi"]).removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        return f"{_BASE}/https://doi.org/{doi}"
    if paper["arxiv_id"]:
        return f"{_BASE}?search={paper['arxiv_id']}&per-page=1"
    raise ValueError("Paper has no DOI or arXiv id")


def get_citation_graph(
    paper_id: str,
    user_id: str | None,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    paper = get_accessible_paper(paper_id, user_id)
    http = client or httpx
    url = _work_url(paper)
    response = http.get(url, timeout=20, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and "results" in payload:
        results = payload.get("results") or []
        if not results:
            raise ValueError("OpenAlex work not found")
        payload = results[0]

    references = []
    reference_ids = payload.get("referenced_works") or []
    if reference_ids:
        filter_value = "|".join(reference_ids[:25])
        ref_response = http.get(
            _BASE,
            params={
                "filter": f"openalex_id:{filter_value}",
                "per-page": 25,
                "select": "id,title,doi,publication_year",
            },
            timeout=20,
            follow_redirects=True,
        )
        ref_response.raise_for_status()
        for item in (ref_response.json().get("results") or []):
            references.append(
                {
                    "openalex_id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "doi": str(item.get("doi") or ""),
                    "year": item.get("publication_year"),
                }
            )

    return {
        "paper_id": paper_id,
        "openalex_id": str(payload.get("id") or ""),
        "cited_by_count": int(payload.get("cited_by_count") or 0),
        "reference_count": len(reference_ids),
        "references": references,
        "source": "openalex",
    }
