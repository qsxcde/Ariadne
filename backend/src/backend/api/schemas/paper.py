"""Paper library and annotation transfer models."""

from typing import Any, Literal

from pydantic import BaseModel, Field

ReadingStatus = Literal["inbox", "queued", "skimming", "reading", "read", "archived"]
AnnotationType = Literal["highlight", "note", "question"]


class PaperBriefSection(BaseModel):
    title: str
    summary: str = ""
    chunk_indexes: list[int] = Field(default_factory=list)


class PaperBrief(BaseModel):
    paper_id: str
    tldr: str
    contributions: list[str] = Field(default_factory=list)
    method: str
    experiments: str
    limitations: str
    takeaways: list[str] = Field(default_factory=list)
    sections: list[PaperBriefSection] = Field(default_factory=list)
    generated_at: str


class PaperSummary(BaseModel):
    id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    url: str | None = None
    reading_status: ReadingStatus = "inbox"
    progress: float = 0.0
    last_read_at: str | None = None
    updated_at: str
    tags: list[str] = Field(default_factory=list)


class PaperDocumentSummary(BaseModel):
    id: str
    filename: str
    status: str
    chunk_count: int
    file_size: int
    parse_quality_status: str | None = None
    updated_at: str


class AnnotationSummary(BaseModel):
    id: str
    type: AnnotationType
    quote: str | None = None
    content: str | None = None
    color: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    bbox: dict[str, float] | None = None
    created_at: str
    updated_at: str


class CollectionSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    paper_count: int = 0
    updated_at: str


class PaperDetail(PaperSummary):
    time_spent_seconds: int = 0
    last_location: dict[str, Any] | None = None
    documents: list[PaperDocumentSummary] = Field(default_factory=list)
    annotations: list[AnnotationSummary] = Field(default_factory=list)
    collections: list[CollectionSummary] = Field(default_factory=list)
    primary_session_id: str | None = None


class ExplainRequest(BaseModel):
    text: str
    mode: Literal["explain", "translate", "simplify"] = "explain"


class ExplainResponse(BaseModel):
    explanation: str


class CollectionAskRequest(BaseModel):
    question: str


class CollectionAskResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    chunk_count: int = 0


class CollectionCompareRequest(BaseModel):
    paper_ids: list[str]


class PaperComparison(BaseModel):
    paper_id: str
    title: str
    method: str
    datasets: str
    metrics: str
    limitations: str


class PaperUpdateRequest(BaseModel):
    title: str | None = None
    authors: list[str] | None = None
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    url: str | None = None
    reading_status: ReadingStatus | None = None
    progress: float | None = Field(default=None, ge=0.0, le=1.0)
    last_location: dict[str, Any] | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)


class AnnotationCreateRequest(BaseModel):
    type: AnnotationType
    quote: str | None = None
    content: str | None = None
    color: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    bbox: dict[str, float] | None = None


class AnnotationUpdateRequest(BaseModel):
    quote: str | None = None
    content: str | None = None
    color: str | None = None


class CollectionCreateRequest(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None


class PaperUploadResponse(BaseModel):
    paper: PaperSummary
    session_id: str
    document_id: str
    job_id: str
    document_status: str
    job_status: str
