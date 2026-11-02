from typing import Any


class PaperParseError(Exception):
    def __init__(self, message: str = "", session_id: str | None = None, document_id: str | None = None):
        self.session_id = session_id
        self.document_id = document_id
        super().__init__(message)


class EmbeddingModelUnavailableError(RuntimeError):
    pass


class UploadValidationError(ValueError):
    """Raised when an upload cannot be accepted (size, magic bytes, metadata)."""


class UploadTooLargeError(UploadValidationError):
    """Raised when the upload exceeds the configured maximum size."""


class InvalidUploadError(UploadValidationError):
    """Raised when the upload payload is not a supported document."""


class SessionNotFoundError(KeyError):
    def __init__(self, message: str = "", session_id: str | None = None):
        self.session_id = session_id
        super().__init__(message)


class ChunkNotFoundError(Exception):
    """Raised when a citation points at a chunk that no longer exists."""

    def __init__(
        self,
        message: str = "",
        session_id: str | None = None,
        document_id: str | None = None,
        chunk_index: int | None = None,
    ):
        self.session_id = session_id
        self.document_id = document_id
        self.chunk_index = chunk_index
        super().__init__(message)


class PaperNotFoundError(Exception):
    """Raised when a paper does not exist or the caller cannot access it."""

    def __init__(self, message: str = "", paper_id: str | None = None):
        self.paper_id = paper_id
        super().__init__(message)


class CollectionNotFoundError(Exception):
    """Raised when a collection does not exist or cannot be accessed."""

    def __init__(self, message: str = "", collection_id: str | None = None):
        self.collection_id = collection_id
        super().__init__(message)


class AnnotationNotFoundError(Exception):
    """Raised when an annotation does not exist or cannot be accessed."""

    def __init__(self, message: str = "", annotation_id: str | None = None):
        self.annotation_id = annotation_id
        super().__init__(message)


class DuplicatePaperError(Exception):
    """Raised when an upload already exists in the caller's library."""

    def __init__(self, message: str = "", paper_id: str | None = None):
        self.paper_id = paper_id
        super().__init__(message)


class ImportResolutionError(ValueError):
    """Raised when an arXiv/DOI/URL identifier cannot be resolved to metadata."""


class ImportFetchError(RuntimeError):
    """Raised when metadata or PDF retrieval fails upstream."""


class DocumentNotFoundError(Exception):
    """Raised when a document does not exist inside the requested session."""

    def __init__(self, message: str = "", session_id: str | None = None, document_id: str | None = None):
        self.session_id = session_id
        self.document_id = document_id
        super().__init__(message)


class JobInProgressError(RuntimeError):
    """Raised when a destructive action races with a running ingestion job."""

    def __init__(self, message: str = "", session_id: str | None = None):
        self.session_id = session_id
        super().__init__(message)


class ActiveIndexNotReadyError(RuntimeError):
    def __init__(self, message: str = "", session_id: str | None = None):
        self.session_id = session_id
        super().__init__(message)


class SnapshotCommitError(RuntimeError):
    """Raised when committing an index snapshot fails, carrying context for rollback/cleanup."""

    def __init__(
        self,
        message: str = "",
        candidate_snapshot: Any | None = None,
        preserve_candidate_snapshot_files: bool = False,
    ):
        self.candidate_snapshot = candidate_snapshot
        self.preserve_candidate_snapshot_files = preserve_candidate_snapshot_files
        super().__init__(message)
