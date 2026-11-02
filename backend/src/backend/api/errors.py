"""Translate domain exceptions into HTTP responses in one place."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.domain.exceptions import (
    AnnotationNotFoundError,
    ChunkNotFoundError,
    CollectionNotFoundError,
    DocumentNotFoundError,
    DuplicatePaperError,
    JobInProgressError,
    PaperNotFoundError,
    SessionNotFoundError,
    UploadTooLargeError,
    UploadValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SessionNotFoundError)
    async def _session_not_found(_request: Request, exc: SessionNotFoundError) -> JSONResponse:
        # SessionNotFoundError subclasses KeyError, whose str() adds quotes.
        detail = str(exc.args[0]) if exc.args else ""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": detail or "Session not found"},
        )

    @app.exception_handler(PaperNotFoundError)
    async def _paper_not_found(_request: Request, exc: PaperNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc) or "Paper not found"},
        )

    @app.exception_handler(CollectionNotFoundError)
    async def _collection_not_found(
        _request: Request, exc: CollectionNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc) or "Collection not found"},
        )

    @app.exception_handler(AnnotationNotFoundError)
    async def _annotation_not_found(
        _request: Request, exc: AnnotationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc) or "Annotation not found"},
        )

    @app.exception_handler(DuplicatePaperError)
    async def _duplicate_paper(_request: Request, exc: DuplicatePaperError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc) or "Paper already exists", "paper_id": exc.paper_id},
        )

    @app.exception_handler(ChunkNotFoundError)
    async def _chunk_not_found(_request: Request, exc: ChunkNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc) or "Source chunk not found"},
        )

    @app.exception_handler(DocumentNotFoundError)
    async def _document_not_found(_request: Request, exc: DocumentNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc) or "Document not found"},
        )

    @app.exception_handler(JobInProgressError)
    async def _job_in_progress(_request: Request, exc: JobInProgressError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc) or "Job in progress"},
        )

    @app.exception_handler(UploadTooLargeError)
    async def _upload_too_large(_request: Request, exc: UploadTooLargeError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            content={"detail": str(exc)},
        )

    @app.exception_handler(UploadValidationError)
    async def _invalid_upload(_request: Request, exc: UploadValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )
