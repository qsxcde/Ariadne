import json

from pydantic import BaseModel

from backend.rag.ingestion.document_ir import DocumentIR, QualityReport
from backend.storage.object_store import get_object_store


class IngestionArtifacts(BaseModel):
    ir_ref: str
    markdown_ref: str
    normalized_markdown_ref: str
    quality_report_ref: str


def save_ingestion_artifacts(
    artifact_prefix: str,
    document_ir: DocumentIR,
    raw_markdown: str,
    normalized_markdown: str,
    quality_report: QualityReport,
) -> IngestionArtifacts:
    """Persist parser artifacts for cache, inspection, and repeatable RAG ingestion."""
    store = get_object_store()
    source_markdown = raw_markdown.strip() or normalized_markdown
    return IngestionArtifacts(
        ir_ref=store.put_bytes(
            f"{artifact_prefix}/document.ir.json",
            _json_dump(document_ir.model_dump(mode="json")).encode("utf-8"),
        ),
        markdown_ref=store.put_bytes(
            f"{artifact_prefix}/document.md",
            (source_markdown.rstrip() + "\n").encode("utf-8"),
        ),
        normalized_markdown_ref=store.put_bytes(
            f"{artifact_prefix}/document.normalized.md",
            (normalized_markdown.rstrip() + "\n").encode("utf-8"),
        ),
        quality_report_ref=store.put_bytes(
            f"{artifact_prefix}/quality_report.json",
            _json_dump(quality_report.model_dump(mode="json")).encode("utf-8"),
        ),
    )


def _json_dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
