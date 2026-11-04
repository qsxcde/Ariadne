"""Paper library endpoints: list, upload, import, export, detail, update, delete."""

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.api.schemas import (
    PaperDetail,
    PaperImportRequest,
    PaperImportResponse,
    PaperSummary,
    PaperUpdateRequest,
    PaperUploadResponse,
)
from backend.api.security import get_current_user
from backend.api.uploads import read_upload_with_limit, reject_by_content_length
from backend.application.library import export as export_service
from backend.application.library import paper_import as paper_import_service
from backend.application.library import papers as paper_service

router = APIRouter()


def _summary(row: dict) -> PaperSummary:
    return PaperSummary(
        id=row["id"],
        title=row["title"],
        authors=row.get("authors") or paper_service.load_authors(row),
        year=row.get("year"),
        venue=row.get("venue"),
        doi=row.get("doi"),
        arxiv_id=row.get("arxiv_id"),
        abstract=row.get("abstract"),
        url=row.get("url"),
        reading_status=row["reading_status"],
        progress=row["progress"],
        last_read_at=row.get("last_read_at"),
        updated_at=row["updated_at"],
        tags=row.get("tags") or [],
    )


@router.get("/papers", response_model=list[PaperSummary])
def list_papers(
    status_filter: str | None = Query(default=None, alias="status"),
    collection_id: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict = Depends(get_current_user),
) -> list[PaperSummary]:
    """文献库列表：按用户、状态、集合、标签与标题过滤。"""
    rows = paper_service.list_library(
        user.get("id") or None,
        reading_status=status_filter,
        collection_id=collection_id,
        tag=tag,
        query=q,
        limit=limit,
    )
    return [_summary(row) for row in rows]


@router.post("/papers", status_code=202, response_model=PaperUploadResponse)
def upload_paper(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> PaperUploadResponse:
    """上传 PDF：创建论文、reading session、文档与摄取任务。"""
    reject_by_content_length(request.headers.get("content-length"))
    pdf_bytes = read_upload_with_limit(file)
    result = paper_service.import_paper_upload(
        user_id=user.get("id") or None,
        filename=file.filename or "paper.pdf",
        mime_type=file.content_type or "application/pdf",
        pdf_bytes=pdf_bytes,
        file_size=file.size,
    )
    paper = result["paper"]
    return PaperUploadResponse(
        paper=_summary(paper),
        session_id=result["session"]["id"],
        document_id=result["document"]["id"],
        job_id=result["job"]["id"],
        document_status=result["document"]["status"],
        job_status=result["job"]["status"],
    )


@router.post("/papers/import", status_code=202, response_model=PaperImportResponse)
def import_paper_by_reference(
    payload: PaperImportRequest,
    user: dict = Depends(get_current_user),
) -> PaperImportResponse:
    """按 arXiv / DOI / 链接导入：抓取元数据，有开放 PDF 时一并入库。"""
    result = paper_import_service.import_paper_reference(
        user_id=user.get("id") or None,
        source=payload.source,
        identifier=payload.identifier,
        download_pdf=payload.download_pdf,
    )
    paper = result["paper"]
    session = result["session"]
    document = result["document"]
    job = result["job"]
    return PaperImportResponse(
        paper=_summary({**paper, "authors": paper_service.load_authors(paper)}),
        pdf_imported=bool(result["pdf_imported"]),
        session_id=session["id"] if session else None,
        document_id=document["id"] if document else None,
        job_id=job["id"] if job else None,
        document_status=document["status"] if document else None,
        job_status=job["status"] if job else None,
        warning=result["warning"],
    )


@router.get("/papers/export.bib", response_class=PlainTextResponse)
def export_bibtex(user: dict = Depends(get_current_user)) -> PlainTextResponse:
    return PlainTextResponse(
        export_service.export_bibtex(user.get("id") or None),
        media_type="application/x-bibtex",
    )


@router.get("/papers/export.csl.json")
def export_csl(user: dict = Depends(get_current_user)) -> JSONResponse:
    return JSONResponse(
        export_service.export_csl_json(user.get("id") or None),
        media_type="application/json",
    )


@router.get("/papers/export.md", response_class=PlainTextResponse)
def export_markdown(user: dict = Depends(get_current_user)) -> PlainTextResponse:
    return PlainTextResponse(
        export_service.export_markdown(user.get("id") or None),
        media_type="text/markdown",
    )


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: str, user: dict = Depends(get_current_user)) -> PaperDetail:
    return PaperDetail(
        **paper_service.get_paper_detail(paper_id, user.get("id") or None)
    )


@router.patch("/papers/{paper_id}", response_model=PaperDetail)
def update_paper(
    paper_id: str,
    payload: PaperUpdateRequest,
    user: dict = Depends(get_current_user),
) -> PaperDetail:
    fields = payload.model_dump(exclude_unset=True)
    return PaperDetail(
        **paper_service.update_paper(
            paper_id, user.get("id") or None, **fields
        )
    )


@router.delete("/papers/{paper_id}")
def delete_paper(paper_id: str, user: dict = Depends(get_current_user)) -> dict:
    """硬删除论文及其会话、文档、批注、集合关联与磁盘产物。"""
    paper_service.delete_paper(paper_id, user.get("id") or None)
    return {"status": "deleted"}
