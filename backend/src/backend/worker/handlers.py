"""Job handlers: bind a job type to its application use case."""

from backend import composition
from backend.application.ingestion.job import run_queued_ingestion_job
from backend.worker.runner import register_handler

DOCUMENT_INGESTION_JOB = "document_ingestion"


def _run_document_ingestion(job: dict) -> None:
    run_queued_ingestion_job(
        job,
        parser_chain_factory=composition.parser_chain,
        embedding_factory=composition.user_embedding,
    )


def register_default_handlers() -> None:
    register_handler(DOCUMENT_INGESTION_JOB, _run_document_ingestion)
