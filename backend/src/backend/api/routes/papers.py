"""Paper library, annotations and collections endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from backend.api.schemas import (
    AnnotationCreateRequest,
    AnnotationSummary,
    AnnotationUpdateRequest,
    CitationGraph,
    CollectionAskRequest,
    CollectionAskResponse,
    CollectionCompareRequest,
    CollectionCreateRequest,
    CollectionSummary,
    CollectionUpdateRequest,
    PaperComparison,
    ExplainRequest,
    ExplainResponse,
    GlossaryResponse,
    LibraryStats,
    PaperBrief,
    PaperDetail,
    PaperImportRequest,
    PaperImportResponse,
    PaperSummary,
    PaperUpdateRequest,
    PaperUploadResponse,
    ReadingStats,
    ReadingTimeRequest,
    ReadingTimeResponse,
    WeeklyReview,
)
from backend.api.security import get_current_user
from backend.api.uploads import read_upload_with_limit, reject_by_content_length
from backend.application import annotations as annotation_service
from backend.application import brief as brief_service
from backend.application import citations as citation_service
from backend.application import collections as collection_service
from backend.application import explain as explain_service
from backend.application import export as export_service
from backend.application import glossary as glossary_service
from backend.application import paper_import as paper_import_service
from backend.application import papers as paper_service
from backend.application import reading as reading_service
from backend.application import review as review_service
from backend.application import stats as stats_service
from backend.application import synthesis as synthesis_service

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


@router.get("/papers/stats", response_model=LibraryStats)
def get_library_stats(user: dict = Depends(get_current_user)) -> LibraryStats:
    return LibraryStats(**stats_service.library_stats(user.get("id") or None))


@router.get("/papers/reading-stats", response_model=ReadingStats)
def get_reading_stats(
    days: int = Query(default=7, ge=1, le=365),
    user: dict = Depends(get_current_user),
) -> ReadingStats:
    """阅读时长统计：按天与按论文聚合，默认最近 7 天。"""
    return ReadingStats(**reading_service.reading_stats(user.get("id") or None, days))


@router.post(
    "/papers/{paper_id}/reading-time",
    status_code=201,
    response_model=ReadingTimeResponse,
)
def record_reading_time(
    paper_id: str,
    payload: ReadingTimeRequest,
    user: dict = Depends(get_current_user),
) -> ReadingTimeResponse:
    """记录一次前台阅读时长（秒），累加到论文总时长与阅读日志。"""
    result = reading_service.record_reading_time(
        paper_id, user.get("id") or None, payload.seconds
    )
    return ReadingTimeResponse(**result)


@router.get("/review/weekly", response_model=WeeklyReview)
def get_weekly_review(user: dict = Depends(get_current_user)) -> WeeklyReview:
    return WeeklyReview(**review_service.weekly_review(user.get("id") or None))


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


@router.post("/papers/{paper_id}/explain", response_model=ExplainResponse)
def explain_selection(
    paper_id: str,
    payload: ExplainRequest,
    user: dict = Depends(get_current_user),
) -> ExplainResponse:
    try:
        explanation = explain_service.explain_selection(
            paper_id,
            user.get("id") or None,
            text=payload.text,
            mode=payload.mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ExplainResponse(explanation=explanation)


@router.get("/papers/{paper_id}/citations", response_model=CitationGraph)
def get_citations(
    paper_id: str, user: dict = Depends(get_current_user)
) -> CitationGraph:
    try:
        return CitationGraph(
            **citation_service.get_citation_graph(paper_id, user.get("id") or None)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAlex failed: {exc}") from exc


@router.get("/papers/{paper_id}/glossary", response_model=GlossaryResponse)
def generate_glossary(
    paper_id: str, user: dict = Depends(get_current_user)
) -> GlossaryResponse:
    try:
        return GlossaryResponse(
            **glossary_service.generate_glossary(paper_id, user.get("id") or None)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/papers/{paper_id}/brief", response_model=PaperBrief)
def generate_brief(
    paper_id: str, user: dict = Depends(get_current_user)
) -> PaperBrief:
    try:
        return PaperBrief(
            **brief_service.generate_paper_brief(paper_id, user.get("id") or None)
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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


@router.get("/papers/{paper_id}/annotations", response_model=list[AnnotationSummary])
def list_annotations(
    paper_id: str,
    type: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[AnnotationSummary]:
    rows = annotation_service.list_for_paper(
        paper_id, user.get("id") or None, annotation_type=type
    )
    return [AnnotationSummary(**row) for row in rows]


@router.post(
    "/papers/{paper_id}/annotations",
    status_code=201,
    response_model=AnnotationSummary,
)
def create_annotation(
    paper_id: str,
    payload: AnnotationCreateRequest,
    user: dict = Depends(get_current_user),
) -> AnnotationSummary:
    try:
        row = annotation_service.create_for_paper(
            paper_id,
            user.get("id") or None,
            annotation_type=payload.type,
            quote=payload.quote,
            content=payload.content,
            color=payload.color,
            document_id=payload.document_id,
            chunk_id=payload.chunk_id,
            page_start=payload.page_start,
            page_end=payload.page_end,
            bbox=payload.bbox,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnnotationSummary(**row)


@router.patch("/annotations/{annotation_id}", response_model=AnnotationSummary)
def update_annotation(
    annotation_id: str,
    payload: AnnotationUpdateRequest,
    user: dict = Depends(get_current_user),
) -> AnnotationSummary:
    try:
        row = annotation_service.update_annotation(
            annotation_id,
            user.get("id") or None,
            quote=payload.quote,
            content=payload.content,
            color=payload.color,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return AnnotationSummary(**row)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: str, user: dict = Depends(get_current_user)
) -> dict:
    annotation_service.delete_annotation(annotation_id, user.get("id") or None)
    return {"status": "deleted"}


@router.post(
    "/collections/{collection_id}/ask", response_model=CollectionAskResponse
)
def ask_collection(
    collection_id: str,
    payload: CollectionAskRequest,
    user: dict = Depends(get_current_user),
) -> CollectionAskResponse:
    try:
        result = synthesis_service.answer_collection(
            collection_id,
            user.get("id") or None,
            payload.question,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CollectionAskResponse(**result)


@router.post(
    "/collections/{collection_id}/compare", response_model=list[PaperComparison]
)
def compare_collection_papers(
    collection_id: str,
    payload: CollectionCompareRequest,
    user: dict = Depends(get_current_user),
) -> list[PaperComparison]:
    try:
        rows = synthesis_service.compare_papers(
            collection_id,
            user.get("id") or None,
            payload.paper_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [PaperComparison(**row) for row in rows]


@router.get("/collections", response_model=list[CollectionSummary])
def list_collections(user: dict = Depends(get_current_user)) -> list[CollectionSummary]:
    return [
        CollectionSummary(**row)
        for row in collection_service.list_for_user(user.get("id") or None)
    ]


@router.post("/collections", status_code=201, response_model=CollectionSummary)
def create_collection(
    payload: CollectionCreateRequest,
    user: dict = Depends(get_current_user),
) -> CollectionSummary:
    return CollectionSummary(
        **collection_service.create_collection(
            user.get("id") or None,
            name=payload.name,
            description=payload.description,
        )
    )


@router.patch("/collections/{collection_id}", response_model=CollectionSummary)
def update_collection(
    collection_id: str,
    payload: CollectionUpdateRequest,
    user: dict = Depends(get_current_user),
) -> CollectionSummary:
    return CollectionSummary(
        **collection_service.update_collection(
            collection_id,
            user.get("id") or None,
            name=payload.name,
            description=payload.description,
            sort_order=payload.sort_order,
        )
    )


@router.put("/collections/{collection_id}/papers/{paper_id}")
def add_paper_to_collection(
    collection_id: str,
    paper_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    collection_service.add_paper(
        collection_id, paper_id, user.get("id") or None
    )
    return {"status": "added"}


@router.delete("/collections/{collection_id}/papers/{paper_id}")
def remove_paper_from_collection(
    collection_id: str,
    paper_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    collection_service.remove_paper(
        collection_id, paper_id, user.get("id") or None
    )
    return {"status": "removed"}
