"""Safe paths and object keys for session artifacts."""

import shutil
from pathlib import Path

from backend.config import data_dir
from backend.storage.object_store import get_object_store


def raw_session_dir(session_id: str) -> Path:
    path = data_dir() / "raw" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def session_storage_prefixes(session_id: str) -> tuple[str, ...]:
    return tuple(f"{root}/{session_id}" for root in ("raw", "parsed", "chunks", "index"))


def remove_session_dir(session_id: str) -> None:
    store = get_object_store()
    for prefix in session_storage_prefixes(session_id):
        store.delete_prefix(prefix)
    root = data_dir().resolve()
    for name in ("raw", "parsed", "chunks", "index"):
        local_dir = (root / name / session_id).resolve()
        if local_dir.is_relative_to(root) and local_dir.is_dir():
            shutil.rmtree(local_dir, ignore_errors=True)


def session_document_file_path(
    session_id: str,
    document_id: str,
    suffix: str = ".pdf",
) -> Path:
    return raw_session_dir(session_id) / f"{document_id}{suffix}"


def session_upload_key(session_id: str, document_id: str, suffix: str = ".pdf") -> str:
    return f"raw/{session_id}/{document_id}{suffix}"


def session_artifact_prefix(session_id: str, document_id: str) -> str:
    return f"raw/{session_id}/parsed/{document_id}"


def session_snapshot_keys(session_id: str, token: str) -> tuple[str, str]:
    base = f"index/{session_id}/snapshots/{token}"
    return f"{base}.faiss.index", f"{base}.chunks.json"


def session_indexes_dir(session_id: str) -> Path:
    path = data_dir() / "index" / session_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def agent_checkpoint_path() -> Path:
    """LangGraph checkpoints live beside, not inside, the application DB."""
    path = data_dir() / "agent"
    path.mkdir(parents=True, exist_ok=True)
    return path / "checkpoints.sqlite"
