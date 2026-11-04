"""Paper library use cases: import, list, detail, reading state and delete."""

import hashlib
import json
import logging
from typing import Any

from backend.adapters.vector import store_cache
from backend.application.ingestion.documents import intake_document_upload
from backend.storage.records import PaperRecord
from backend.domain.access import paper_is_accessible
from backend.domain.exceptions import (
    DuplicatePaperError,
    JobInProgressError,
    PaperNotFoundError,
)
from backend.storage.paths import remove_session_dir
from backend.storage.sqlite import annotations as annotation_repo
from backend.storage.sqlite import collections as collection_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import jobs as job_repo
from backend.storage.sqlite import papers as paper_repo
from backend.storage.sqlite import sessions as session_repo

logger = logging.getLogger(__name__)


def _paper_title(filename: str) -> str:
    title = filename.strip()
    if title.lower().endswith(".pdf"):
        title = title[:-4]
    return title or "Untitled"


def load_authors(paper: PaperRecord) -> list[str]:
    raw = paper.get("authors_json")
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def load_last_location(paper: PaperRecord) -> dict[str, Any] | None:
    raw = paper.get("last_location_json")
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def serialize_authors(authors: list[str] | None) -> str | None:
    if authors is None:
        return None
    return json.dumps([item.strip() for item in authors if item.strip()], ensure_ascii=False)


def get_accessible_paper(paper_id: str, user_id: str | None) -> PaperRecord:
    paper = paper_repo.get_paper(paper_id)
    if not paper_is_accessible(paper, user_id):
        raise PaperNotFoundError(f"Paper not found: {paper_id}", paper_id=paper_id)
    assert paper is not None
    return paper


def list_library(
    user_id: str | None,
    *,
    reading_status: str | None = None,
    collection_id: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    papers = paper_repo.list_papers(
        user_id,
        reading_status=reading_status,
        collection_id=collection_id,
        tag=tag,
        query=query,
        limit=limit,
    )
    return [
        {**paper, "authors": load_authors(paper), "tags": collection_repo.list_tags(paper["id"])}
        for paper in papers
    ]


def get_paper_detail(paper_id: str, user_id: str | None) -> dict[str, Any]:
    paper = get_accessible_paper(paper_id, user_id)
    documents = document_repo.list_documents_for_paper(paper_id)
    sessions = session_repo.list_sessions_for_paper(paper_id)
    annotations = annotation_repo.list_annotations(paper_id)
    collections = [
        collection
        for collection in collection_repo.list_collections_for_paper(paper_id)
        if collection.get("user_id") in (None, user_id)
    ]
    return {
        **paper,
        "authors": load_authors(paper),
        "tags": collection_repo.list_tags(paper_id),
        "last_location": load_last_location(paper),
        "documents": documents,
        "annotations": annotations,
        "collections": collections,
        "primary_session_id": sessions[0]["id"] if sessions else None,
    }


def import_paper_upload(
    *,
    user_id: str | None,
    filename: str,
    mime_type: str,
    pdf_bytes: bytes,
    file_size: int | None = None,
) -> dict[str, Any]:
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    duplicate = paper_repo.find_by_file_hash(user_id, file_hash)
    if duplicate is not None:
        raise DuplicatePaperError(
            f"Paper already exists: {duplicate['title']}",
            paper_id=duplicate["id"],
        )

    session = session_repo.create_session(_paper_title(filename), user_id=user_id)
    try:
        intake = intake_document_upload(
            session_id=session["id"],
            filename=filename,
            mime_type=mime_type,
            pdf_bytes=pdf_bytes,
            file_size=file_size,
            file_hash=file_hash,
        )
    except Exception:
        session_repo.archive_session(session["id"])
        raise

    paper = paper_repo.get_paper(intake["document"]["paper_id"])
    if paper is None:
        raise RuntimeError("创建论文失败")
    return {
        "paper": paper,
        "session": session_repo.get_session(session["id"]) or session,
        "document": intake["document"],
        "job": intake["job"],
    }


def update_paper(
    paper_id: str,
    user_id: str | None,
    *,
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    venue: str | None = None,
    doi: str | None = None,
    arxiv_id: str | None = None,
    abstract: str | None = None,
    url: str | None = None,
    reading_status: str | None = None,
    progress: float | None = None,
    last_location: dict[str, Any] | None = None,
    time_spent_seconds: int | None = None,
) -> dict[str, Any]:
    get_accessible_paper(paper_id, user_id)
    paper_repo.update_paper_metadata(
        paper_id,
        title=title,
        authors_json=serialize_authors(authors),
        year=year,
        venue=venue,
        doi=doi,
        arxiv_id=arxiv_id,
        abstract=abstract,
        url=url,
    )
    paper_repo.update_reading_state(
        paper_id,
        reading_status=reading_status,
        progress=progress,
        last_location_json=json.dumps(last_location, ensure_ascii=False)
        if last_location is not None
        else None,
        time_spent_seconds=time_spent_seconds,
    )
    return get_paper_detail(paper_id, user_id)


def delete_paper(paper_id: str, user_id: str | None) -> None:
    """硬删除论文：会话、文档、分块、批注、集合关联、阅读日志与磁盘产物。

    索引快照与 FAISS 缓存随会话目录一并清理；摄取未结束时拒绝删除，
    避免 worker 边写 chunk 边被删（FK 冲突）。
    """
    get_accessible_paper(paper_id, user_id)

    active_sessions = session_repo.list_sessions_for_paper(paper_id)
    for session in active_sessions:
        if job_repo.has_running_job(session["id"]):
            raise JobInProgressError(
                "Paper is still being processed, try again later.",
                session_id=session["id"],
            )

    session_ids = paper_repo.delete_paper(paper_id)

    # 文档的 PDF/解析产物都在会话目录下，随 remove_session_dir 一并清理。
    for session_id in session_ids:
        store_cache.discard_store(session_id)
        remove_session_dir(session_id)
