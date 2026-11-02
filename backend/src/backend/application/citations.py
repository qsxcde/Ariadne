"""OpenAlex citation graph for one paper."""

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from backend.application.papers import get_accessible_paper

_BASE = "https://api.openalex.org/works"
_ARXIV_VERSION = re.compile(r"v\d+$")


def _normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _titles_match(left: str, right: str) -> bool:
    """Guard against OpenAlex full-text search returning an unrelated work."""
    a, b = _normalize_title(left), _normalize_title(right)
    if not a or not b:
        return False
    return a in b or b in a or a[:80] == b[:80]


def _work_url(paper: Mapping[str, Any]) -> str:
    if paper["doi"]:
        doi = str(paper["doi"]).removeprefix("https://doi.org/").removeprefix("http://doi.org/")
        return f"{_BASE}/https://doi.org/{doi}"
    title = str(paper.get("title") or "").strip()
    if title:
        # arXiv id 的全文检索会命中「提到该 id」的无关论文，按标题检索更可靠。
        return f"{_BASE}?filter=title.search:{quote(title[:200])}&per-page=1"
    if paper["arxiv_id"]:
        # 兜底：OpenAlex 索引的是不带版本号的 arXiv id。
        arxiv_id = _ARXIV_VERSION.sub("", str(paper["arxiv_id"]))
        return f"{_BASE}?search={arxiv_id}&per-page=1"
    raise ValueError("Paper has no DOI, title or arXiv id")


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
        candidate = results[0]
        if paper["doi"] is None and not _titles_match(
            str(paper.get("title") or ""), str(candidate.get("title") or "")
        ):
            raise ValueError("OpenAlex work not found for this title")
        payload = candidate

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
