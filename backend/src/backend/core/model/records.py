"""Typed shapes returned by the SQLite repositories.

These are dicts at runtime (zero-cost), but they give mypy a contract so call
sites using the wrong key (e.g. document["state"]) fail at check time.
"""

from typing import TypedDict


class DocumentRecord(TypedDict):
    id: str
    paper_id: str
    session_id: str
    filename: str
    file_path: str
    mime_type: str
    file_size: int
    file_hash: str | None
    chunk_count: int
    status: str
    error_message: str | None
    created_at: str
    updated_at: str
    parsed_ir_path: str | None
    parsed_markdown_path: str | None
    quality_report_path: str | None
    parser_name: str | None
    parser_version: str | None
    parse_quality_status: str | None


class MessageRecord(TypedDict):
    id: str
    session_id: str
    role: str
    content: str
    sources: list[dict]
    status: str
    client_message_id: str | None
    model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    created_at: str
class JobRecord(TypedDict):
    id: str
    paper_id: str | None
    session_id: str
    document_id: str | None
    type: str
    status: str
    stage: str
    attempt: int
    error_message: str | None
    payload_json: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
class SessionRecord(TypedDict):
    id: str
    title: str
    user_id: str | None
    paper_id: str | None
    created_at: str
    updated_at: str
    last_opened_at: str
    is_archived: int
    is_pinned: int


class NotificationRecord(TypedDict):
    id: str
    user_id: str | None
    kind: str
    title: str
    body: str
    status: str
    created_at: str
    delivered_at: str | None


class AlertSettingsRecord(TypedDict):
    id: str
    user_id: str | None
    new_paper: int
    new_version: int
    new_citation: int
    digest_enabled: int
    digest_frequency: str
    updated_at: str


class SubscriptionRecord(TypedDict):
    id: str
    user_id: str | None
    kind: str
    value: str
    is_active: int
    created_at: str
    last_checked_at: str | None


class FeedItemRecord(TypedDict):
    id: str
    user_id: str | None
    source: str
    external_id: str
    title: str
    authors_json: str | None
    abstract: str | None
    url: str | None
    published_at: str | None
    paper_id: str | None
    status: str
    relevance_reason: str | None
    created_at: str


class CollectionRecord(TypedDict):
    id: str
    user_id: str | None
    name: str
    description: str | None
    sort_order: int
    created_at: str
    updated_at: str


class AnnotationRecord(TypedDict):
    id: str
    paper_id: str
    document_id: str | None
    chunk_id: str | None
    type: str
    quote: str | None
    content: str | None
    color: str | None
    page_start: int | None
    page_end: int | None
    bbox_json: str | None
    created_at: str
    updated_at: str


class PaperRecord(TypedDict):
    id: str
    user_id: str | None
    title: str
    authors_json: str | None
    year: int | None
    venue: str | None
    doi: str | None
    arxiv_id: str | None
    abstract: str | None
    url: str | None
    metadata_json: str | None
    reading_status: str
    progress: float
    last_location_json: str | None
    last_read_at: str | None
    time_spent_seconds: int
    last_citation_count: int | None
    last_arxiv_updated: str | None
    created_at: str
    updated_at: str


class IndexRecord(TypedDict):
    id: str
    session_id: str
    index_path: str
    chunks_path: str
    status: str
    created_at: str
    updated_at: str
class SessionSummaryRecord(SessionRecord):
    document_count: int
    message_count: int
    indexed_chunks: int


class SnapshotRecord(TypedDict):
    id: str
    session_id: str
    status: str
    index_path: str
    chunks_path: str
    document_ids: list[str]
    error_message: str | None
    created_at: str
    updated_at: str
