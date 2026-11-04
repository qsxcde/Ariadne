import json
import uuid
from typing import Literal, cast

from backend.core.model.records import JobRecord

from backend.domain.states import DocumentStage
from backend.domain.states import JobStatus
from backend.domain.states import TERMINAL_JOB_STATUSES
from backend.storage.sqlite.connection import connect
from backend.storage.sqlite.connection import row_to_dict
from backend.storage.sqlite.connection import transaction
from backend.storage.sqlite.sessions import now_iso


def create_job(
    session_id: str,
    document_id: str | None,
    job_type: str,
    stage: DocumentStage,
    payload_json: str | None = None,
) -> JobRecord:

    job_id = str(uuid.uuid4())
    timestamp = now_iso()
    paper_id: str | None = None
    if document_id is not None:
        with connect() as conn:
            row = conn.execute(
                "SELECT paper_id FROM documents WHERE id = ?", (document_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError(f"Document not found: {document_id}")
        paper_id = row["paper_id"]

    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
              id, paper_id, session_id, document_id, type, status, stage, attempt,
              error_message, payload_json, created_at, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, 'queued', ?, 0, NULL, ?, ?, NULL, NULL)
            """,
            (job_id, paper_id, session_id, document_id, job_type, stage, payload_json, timestamp),
        )
    job = get_job(job_id)
    if job is None:
        raise RuntimeError("创建任务失败")
    return job


def list_runnable_jobs(limit: int = 10) -> list[JobRecord]:

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [cast(JobRecord, dict(row)) for row in rows]


def list_running_jobs(limit: int = 10) -> list[JobRecord]:

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status IN (?, ?)
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (JobStatus.running, JobStatus.interrupted, limit),
        ).fetchall()
        return [cast(JobRecord, dict(row)) for row in rows]


def list_jobs_for_session(session_id: str) -> list[JobRecord]:

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM jobs
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        ).fetchall()
        return [cast(JobRecord, dict(row)) for row in rows]


def mark_job_running(job_id: str) -> bool:

    with transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                attempt = attempt + 1,
                error_message = NULL,
                started_at = ?,
                finished_at = NULL
            WHERE id = ? AND status = 'queued'
            """,
            (now_iso(), job_id),
        )
    return cursor.rowcount > 0


def requeue_interrupted_job(job_id: str) -> bool:

    with transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                error_message = NULL,
                started_at = NULL,
                finished_at = NULL
            WHERE id = ? AND status IN (?, ?)
            """,
            (
                JobStatus.queued,
                job_id,
                JobStatus.running,
                JobStatus.interrupted,
            ),
        )
    return cursor.rowcount > 0


def mark_job_finished(
    job_id: str,
    status: Literal[
        JobStatus.succeeded,
        JobStatus.failed,
        JobStatus.cancelled,
        JobStatus.interrupted,
    ],
    error_message: str | None = None,
) -> bool:
    if status not in TERMINAL_JOB_STATUSES:
        raise ValueError("任务只能以终态结束")

    with transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                error_message = ?,
                finished_at = ?
            WHERE id = ? AND status = ?
            """,
            (status, error_message, now_iso(), job_id, JobStatus.running),
        )
    return cursor.rowcount > 0


def get_job(job_id: str) -> JobRecord | None:

    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return cast(JobRecord | None, row_to_dict(row))


def update_job_payload(job_id: str, updates: dict[str, object]) -> bool:
    """Merge keys into a job's payload without replacing unrelated fields."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT payload_json FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return False
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.update(updates)
        conn.execute(
            "UPDATE jobs SET payload_json = ? WHERE id = ?",
            (json.dumps(payload, ensure_ascii=False), job_id),
        )
    return True


def has_running_job(session_id: str) -> bool:
    """Whether the session still has a job in the running state."""
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE session_id = ? AND status = ? LIMIT 1",
            (session_id, JobStatus.running),
        ).fetchone()
    return row is not None
