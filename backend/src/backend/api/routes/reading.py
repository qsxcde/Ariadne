"""Reading assistance, progress, stats and weekly review endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.schemas import (
    CitationGraph,
    ExplainRequest,
    ExplainResponse,
    GlossaryResponse,
    LibraryStats,
    PaperBrief,
    ReadingStats,
    ReadingTimeRequest,
    ReadingTimeResponse,
    WeeklyNoteRequest,
    WeeklyReview,
)
from backend.api.deps import get_text_completer
from backend.api.security import get_current_user
from backend.application.reading import brief as brief_service
from backend.application.library import citations as citation_service
from backend.application.reading import explain as explain_service
from backend.application.reading import glossary as glossary_service
from backend.application.reading import progress as reading_service
from backend.application.reading import review as review_service
from backend.application.reading import stats as stats_service
from backend.domain.ports import TextCompleter

router = APIRouter()


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


@router.put("/review/weekly/note", response_model=WeeklyReview)
def save_weekly_note(
    payload: WeeklyNoteRequest,
    user: dict = Depends(get_current_user),
) -> WeeklyReview:
    """保存本周复盘文字，返回更新后的周报。"""
    return WeeklyReview(
        **review_service.save_weekly_note(user.get("id") or None, payload.note)
    )


@router.post("/papers/{paper_id}/explain", response_model=ExplainResponse)
def explain_selection(
    paper_id: str,
    payload: ExplainRequest,
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
) -> ExplainResponse:
    try:
        explanation = explain_service.explain_selection(
            paper_id,
            user.get("id") or None,
            text=payload.text,
            mode=payload.mode,
            completer=completer,
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
    paper_id: str,
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
) -> GlossaryResponse:
    try:
        return GlossaryResponse(
            **glossary_service.generate_glossary(
                paper_id, user.get("id") or None, completer=completer
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Glossary generation failed: {exc}") from exc


@router.post("/papers/{paper_id}/brief", response_model=PaperBrief)
def generate_brief(
    paper_id: str,
    force: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
) -> PaperBrief:
    try:
        return PaperBrief(
            **brief_service.generate_paper_brief(
                paper_id, user.get("id") or None, force=force, completer=completer
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
