"""Import papers from arXiv, DOI or a landing-page URL (M1.2.1)."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx

from backend.application.papers import import_paper_upload, serialize_authors
from backend.domain.exceptions import (
    DuplicatePaperError,
    ImportFetchError,
    ImportResolutionError,
)
from backend.storage.sqlite import papers as paper_repo

ARXIV_API_URL = "https://export.arxiv.org/api/query"
CROSSREF_API_URL = "https://api.crossref.org/works"
USER_AGENT = "SciPal/0.1 (paper import)"
MAX_PDF_BYTES = 40 * 1024 * 1024

_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV = "{http://arxiv.org/schemas/atom}"
_VERSION_SUFFIX = re.compile(r"v\d+$")
_ARXIV_NEW = re.compile(r"^\d{4}\.\d{4,5}$")
_ARXIV_OLD = re.compile(r"^[a-z\-]+(?:\.[a-z]{2})?/\d{7}$", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class PaperReference:
    """Metadata resolved from an external identifier, before it becomes a paper."""

    source: str
    identifier: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    url: str | None = None
    pdf_url: str | None = None


def normalize_arxiv_id(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ImportResolutionError("arXiv 标识不能为空")
    match = re.search(r"arxiv\.org/(?:abs|pdf)/([^?#]+)", value, re.IGNORECASE)
    if match:
        value = match.group(1)
    value = re.sub(r"^arxiv:\s*", "", value, flags=re.IGNORECASE).strip().rstrip("/")
    if value.lower().endswith(".pdf"):
        value = value[:-4]
    value = _VERSION_SUFFIX.sub("", value)
    if not (_ARXIV_NEW.match(value) or _ARXIV_OLD.match(value)):
        raise ImportResolutionError(f"无法识别的 arXiv 标识：{raw}")
    return value


def normalize_doi(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    if not value.lower().startswith("10.") or "/" not in value:
        raise ImportResolutionError(f"无法识别的 DOI：{raw}")
    return value


def normalize_url(raw: str) -> str:
    value = raw.strip()
    if not value.lower().startswith(("http://", "https://")):
        raise ImportResolutionError(f"需要 http(s) 链接：{raw}")
    return value


def _clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _strip_markup(value: str | None) -> str:
    return _clean_text(_TAGS.sub(" ", value or ""))


def _year_from(value: str | None) -> int | None:
    match = re.search(r"(\d{4})", value or "")
    return int(match.group(1)) if match else None


def _first(values: list[str] | None) -> str | None:
    for value in values or []:
        cleaned = _clean_text(value)
        if cleaned:
            return cleaned
    return None


def _safe_filename(identifier: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", identifier).strip("._")
    return f"{slug or 'paper'}.pdf"


def _http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 20,
) -> httpx.Response:
    """Single HTTP entry point so tests can stub every external call."""
    try:
        response = httpx.get(
            url,
            params=params,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ImportFetchError(f"抓取失败：{url}（{exc}）") from exc
    return response


def fetch_arxiv_reference(identifier: str) -> PaperReference:
    arxiv_id = normalize_arxiv_id(identifier)
    response = _http_get(ARXIV_API_URL, params={"id_list": arxiv_id})
    try:
        root = ElementTree.fromstring(response.text)
    except ElementTree.ParseError as exc:
        raise ImportFetchError("arXiv 返回内容无法解析") from exc
    entry = root.find(f"{_ATOM}entry")
    if entry is None:
        raise ImportResolutionError(f"arXiv 未找到论文：{arxiv_id}")
    title = _clean_text(entry.findtext(f"{_ATOM}title"))
    if not title or title.lower() == "error":
        raise ImportResolutionError(f"arXiv 未找到论文：{arxiv_id}")

    authors = [
        _clean_text(author.findtext(f"{_ATOM}name"))
        for author in entry.findall(f"{_ATOM}author")
    ]
    pdf_url = None
    for link in entry.findall(f"{_ATOM}link"):
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            pdf_url = link.get("href")
            break
    return PaperReference(
        source="arxiv",
        identifier=arxiv_id,
        title=title,
        authors=[name for name in authors if name],
        year=_year_from(entry.findtext(f"{_ATOM}published")),
        venue=_clean_text(entry.findtext(f"{_ARXIV}journal_ref")) or "arXiv",
        doi=_clean_text(entry.findtext(f"{_ARXIV}doi")) or None,
        arxiv_id=arxiv_id,
        abstract=_clean_text(entry.findtext(f"{_ATOM}summary")) or None,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
    )


def fetch_doi_reference(identifier: str) -> PaperReference:
    doi = normalize_doi(identifier)
    response = _http_get(f"{CROSSREF_API_URL}/{doi}")
    try:
        message = response.json().get("message") or {}
    except ValueError as exc:
        raise ImportFetchError("Crossref 返回内容无法解析") from exc

    title = _clean_text(" ".join(message.get("title") or []))
    if not title:
        raise ImportResolutionError(f"Crossref 未找到论文：{doi}")

    authors: list[str] = []
    for author in message.get("author") or []:
        name = " ".join(
            part for part in (author.get("given"), author.get("family")) if part
        ).strip()
        if name:
            authors.append(name)

    year = None
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (message.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break

    pdf_url = None
    for link in message.get("link") or []:
        if link.get("content-type") == "application/pdf" and link.get("URL"):
            pdf_url = str(link["URL"])
            break

    venues = message.get("container-title") or []
    return PaperReference(
        source="doi",
        identifier=doi,
        title=title,
        authors=authors,
        year=year,
        venue=_clean_text(venues[0]) if venues else None,
        doi=doi,
        abstract=_strip_markup(message.get("abstract")) or None,
        url=str(message.get("URL") or f"https://doi.org/{doi}"),
        pdf_url=pdf_url,
    )


class _MetaCollector(HTMLParser):
    """Collect citation_* / og:* meta tags plus the <title> element."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "meta":
            key = (attributes.get("name") or attributes.get("property") or "").lower()
            content = attributes.get("content", "").strip()
            if key and content:
                self.meta.setdefault(key, []).append(content)
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)


def fetch_url_reference(identifier: str) -> PaperReference:
    url = normalize_url(identifier)
    response = _http_get(url)
    if "pdf" in response.headers.get("content-type", "").lower():
        stem = url.rstrip("/").rsplit("/", 1)[-1]
        title = re.sub(r"\.pdf$", "", stem, flags=re.IGNORECASE) or url
        return PaperReference(
            source="url", identifier=url, title=title, url=url, pdf_url=url
        )

    collector = _MetaCollector()
    collector.feed(response.text)
    meta = collector.meta
    page_title = _first(meta.get("citation_title")) or _first(meta.get("og:title"))
    page_title = page_title or _first(collector.title_parts)
    if not page_title:
        raise ImportResolutionError(f"页面没有可识别的标题：{url}")

    pdf_url = _first(meta.get("citation_pdf_url"))
    return PaperReference(
        source="url",
        identifier=url,
        title=page_title,
        authors=meta.get("citation_author") or meta.get("dc.creator") or [],
        year=_year_from(
            _first(meta.get("citation_publication_date"))
            or _first(meta.get("citation_date"))
            or _first(meta.get("dc.date"))
        ),
        venue=_first(meta.get("citation_journal_title"))
        or _first(meta.get("citation_conference_title"))
        or _first(meta.get("og:site_name")),
        doi=_first(meta.get("citation_doi")),
        abstract=_first(meta.get("citation_abstract"))
        or _first(meta.get("og:description")),
        url=url,
        pdf_url=urljoin(url, pdf_url) if pdf_url else None,
    )


_RESOLVERS = {
    "arxiv": fetch_arxiv_reference,
    "doi": fetch_doi_reference,
    "url": fetch_url_reference,
}


def resolve_reference(source: str, identifier: str) -> PaperReference:
    resolver = _RESOLVERS.get(source.strip().lower())
    if resolver is None:
        raise ImportResolutionError(f"不支持的导入来源：{source}")
    return resolver(identifier)


def _download_pdf(url: str) -> bytes | None:
    response = _http_get(url, timeout=60)
    content = response.content
    if len(content) > MAX_PDF_BYTES:
        raise ImportFetchError(f"PDF 超过 {MAX_PDF_BYTES // (1024 * 1024)}MB 上限")
    if not content.startswith(b"%PDF"):
        return None
    return content


def _find_existing(user_id: str | None, reference: PaperReference) -> Any:
    if reference.arxiv_id:
        found = paper_repo.find_by_arxiv_id(user_id, reference.arxiv_id)
        if found is not None:
            return found
    if reference.doi:
        return paper_repo.find_by_doi(user_id, reference.doi)
    return None


def import_paper_reference(
    *,
    user_id: str | None,
    source: str,
    identifier: str,
    download_pdf: bool = True,
) -> dict[str, Any]:
    """Resolve an identifier and add it to the library, with a PDF when available."""
    reference = resolve_reference(source, identifier)
    existing = _find_existing(user_id, reference)
    if existing is not None:
        raise DuplicatePaperError(
            f"Paper already exists: {existing['title']}", paper_id=existing["id"]
        )

    warning: str | None = None
    pdf_bytes: bytes | None = None
    if download_pdf:
        if reference.pdf_url:
            try:
                pdf_bytes = _download_pdf(reference.pdf_url)
            except ImportFetchError as exc:
                warning = f"PDF 下载失败，仅导入元数据：{exc}"
            if pdf_bytes is None and warning is None:
                warning = "来源返回的内容不是 PDF，仅导入元数据"
        else:
            warning = "来源未提供可下载的 PDF，仅导入元数据"

    metadata: dict[str, Any] = {
        "title": reference.title,
        "authors_json": serialize_authors(reference.authors),
        "year": reference.year,
        "venue": reference.venue,
        "doi": reference.doi,
        "arxiv_id": reference.arxiv_id,
        "abstract": reference.abstract,
        "url": reference.url,
    }

    if pdf_bytes is not None:
        intake = import_paper_upload(
            user_id=user_id,
            filename=_safe_filename(reference.arxiv_id or reference.identifier),
            mime_type="application/pdf",
            pdf_bytes=pdf_bytes,
            file_size=len(pdf_bytes),
        )
        paper = paper_repo.update_paper_metadata(intake["paper"]["id"], **metadata)
        return {
            "paper": paper or intake["paper"],
            "session": intake["session"],
            "document": intake["document"],
            "job": intake["job"],
            "pdf_imported": True,
            "warning": warning,
        }

    paper = paper_repo.create_paper(user_id=user_id, **metadata)
    return {
        "paper": paper,
        "session": None,
        "document": None,
        "job": None,
        "pdf_imported": False,
        "warning": warning or "未导入 PDF，可稍后上传原文",
    }
