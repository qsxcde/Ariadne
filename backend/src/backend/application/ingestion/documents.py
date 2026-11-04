import json
import logging
import re
import shutil
import uuid
from contextlib import suppress
from pathlib import Path, PurePosixPath

from backend.adapters.pdf.cropper import CropRenderError, render_block_crop
from backend.application.ingestion import index_maintenance
from backend.config import data_dir, settings
from backend.rag.ingestion.text_sanitizer import wrap_bare_latex
from backend.storage.records import DocumentRecord
from backend.domain.exceptions import (
    BlockCropError,
    ChunkNotFoundError,
    JobInProgressError,
    DocumentNotFoundError,
    InvalidUploadError,
    SessionNotFoundError,
    UploadTooLargeError,
)
from backend.domain.states import DocumentStage
from backend.domain.ports import EmbeddingRuntime
from backend.storage.object_store import get_object_store
from backend.storage.paths import session_artifact_prefix, session_upload_key
from backend.storage.sqlite import chunks as chunk_repo
from backend.storage.sqlite import documents as document_repo
from backend.storage.sqlite import jobs as job_repo
from backend.storage.sqlite import sessions as session_repo

logger = logging.getLogger(__name__)

_BLOCK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CROP_SCALE_MIN = 1
_CROP_SCALE_MAX = 3


def _validate_upload(file_size: int | None, pdf_bytes: bytes) -> None:
    if file_size is None:
        raise InvalidUploadError("Cannot determine file size")
    if file_size > settings.upload_max_bytes:
        raise UploadTooLargeError(f"File too large (max {settings.upload_max_bytes} bytes)")
    if not pdf_bytes.startswith(b"%PDF"):
        raise InvalidUploadError("Uploaded file is not a valid PDF")


def intake_document_upload(
    session_id: str,
    filename: str,
    mime_type: str,
    pdf_bytes: bytes,
    file_size: int | None = None,
    file_hash: str | None = None,
) -> dict:
    """Persist upload intake state and enqueue an ingestion job."""
    _validate_upload(file_size or len(pdf_bytes), pdf_bytes)
    session = session_repo.get_session(session_id)
    if session is None:
        raise SessionNotFoundError(
            f"Session not found: {session_id}", session_id=session_id
        )
    document_id = str(uuid.uuid4())
    store = get_object_store()
    file_path = store.put_bytes(
        session_upload_key(session_id, document_id), pdf_bytes
    )
    document = None
    job = None
    try:
        document = document_repo.create_document(
            session_id=session_id,
            filename=filename,
            file_path=str(file_path),
            mime_type=mime_type,
            file_size=len(pdf_bytes),
            document_id=document_id,
            file_hash=file_hash,
        )
        job = job_repo.create_job(
            session_id=session_id,
            document_id=document_id,
            job_type="document_ingestion",
            stage=DocumentStage.uploaded,
            payload_json=json.dumps(
                {
                    "document_id": document_id,
                    "filename": filename,
                    "file_path": str(file_path),
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        with suppress(RuntimeError, OSError):
            document_repo.delete_document(document_id)
        with suppress(OSError, ValueError):
            store.delete(file_path)
        raise

    session_repo.touch_session(session_id)
    with suppress(RuntimeError, OSError):
        if session["title"] == settings.msg_default_session_title:
            session_repo.update_session_title(session_id, document["filename"])
    return {
        "document": document,
        "job": job,
    }


def get_source_chunk(session_id: str, document_id: str, chunk_index: int) -> dict:
    """Resolve a citation back to its full chunk text for the reader panel."""
    chunk = chunk_repo.get_chunk(session_id, document_id, chunk_index)
    if chunk is None:
        raise ChunkNotFoundError(
            f"Source chunk not found: document={document_id} chunk={chunk_index}",
            session_id=session_id,
            document_id=document_id,
            chunk_index=chunk_index,
        )
    metadata = chunk.metadata
    block_ids = metadata.block_ids or []
    document = document_repo.get_document(document_id)
    return {
        "document_id": document_id,
        "chunk_index": metadata.chunk_index,
        "section": metadata.section,
        "section_path": metadata.section_path or [],
        "page_start": metadata.page_start,
        "page_end": metadata.page_end,
        "type": metadata.type,
        "text": chunk.text,
        "block_ids": block_ids,
        "blocks": _resolve_block_boxes(
            document.get("parsed_ir_path") if document else None,
            block_ids,
        ),
    }


def get_document_file(session_id: str, document_id: str) -> Path:
    """Materialize the stored PDF for download."""
    document = _get_owned_document(session_id, document_id)
    ref = str(document["file_path"])
    if Path(ref).is_absolute() and not Path(ref).resolve().is_relative_to(
        data_dir().resolve()
    ):
        raise DocumentNotFoundError(
            f"Document file not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        )
    try:
        path = get_object_store().materialize(ref)
    except (FileNotFoundError, ValueError) as exc:
        raise DocumentNotFoundError(
            f"Document file not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        ) from exc
    if not path.is_file():
        raise DocumentNotFoundError(
            f"Document file not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        )
    return path


def get_block_crop(
    session_id: str,
    document_id: str,
    block_id: str,
    scale: int = 2,
) -> bytes:
    """Render one reader block from the stored PDF, cached beside the IR."""
    if not _BLOCK_ID_PATTERN.fullmatch(block_id):
        raise BlockCropError(
            "Invalid block id",
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        )

    document = _get_owned_document(session_id, document_id)
    ir_path = document.get("parsed_ir_path")
    if not ir_path:
        raise BlockCropError(
            "Parsed content is not available",
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        )
    payload = _load_ir_payload(ir_path)
    if payload is None:
        raise BlockCropError(
            "Parsed content is not available",
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        )

    block = next(
        (item for item in _iter_ir_blocks(payload) if item.get("id") == block_id),
        None,
    )
    if block is None:
        raise BlockCropError(
            f"Block not found: {block_id}",
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        )

    page_number = int(block.get("page_number") or 0)
    pages = {page.get("page_number"): page for page in payload.get("pages") or []}
    bbox = _normalize_bbox(
        block.get("bbox"),
        pages.get(page_number),
        str(payload.get("bbox_unit") or "points"),
    )
    if bbox is None:
        raise BlockCropError(
            "Block has no usable bounding box",
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        )

    artifact_prefix = session_artifact_prefix(session_id, document_id)
    store = get_object_store()
    scale = max(_CROP_SCALE_MIN, min(_CROP_SCALE_MAX, int(scale)))
    cache_ref = f"{artifact_prefix}/crops/{block_id}-{scale}x.png"
    if store.exists(cache_ref):
        return store.get_bytes(cache_ref)

    pdf_path = get_document_file(session_id, document_id)
    try:
        image = render_block_crop(
            pdf_path,
            page_number,
            bbox,
            scale=float(scale),
        )
    except CropRenderError as exc:
        raise BlockCropError(
            str(exc),
            session_id=session_id,
            document_id=document_id,
            block_id=block_id,
        ) from exc

    store.put_bytes(cache_ref, image)
    return image


def _get_owned_document(
    session_id: str, document_id: str
) -> DocumentRecord:
    document = document_repo.get_document(document_id)
    if document is None or document["session_id"] != session_id:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        )
    return document


def _resolve_block_boxes(ir_path: str | None, block_ids: list[str]) -> list[dict]:
    """Map cited block ids to page numbers and normalized (0-1) boxes.

    The IR stores bbox in PDF points; normalizing here keeps the frontend free
    of page-size math and works for any render scale.
    """
    if not ir_path or not block_ids:
        return []
    payload = _load_ir_payload(ir_path)
    if payload is None:
        return []

    wanted = set(block_ids)
    pages = {page.get("page_number"): page for page in payload.get("pages") or []}
    bbox_unit = str(payload.get("bbox_unit") or "points")
    boxes: list[dict] = []
    for block in _iter_ir_blocks(payload):
        if block.get("id") not in wanted:
            continue
        page_number = block.get("page_number") or 0
        boxes.append(
            {
                "id": block["id"],
                "page_number": page_number,
                "bbox": _normalize_bbox(
                    block.get("bbox"),
                    pages.get(page_number),
                    bbox_unit,
                ),
            }
        )
    return boxes


def _normalize_bbox(
    bbox: object,
    page: dict | None,
    bbox_unit: str = "points",
) -> dict[str, float] | None:
    if not isinstance(bbox, dict):
        return None
    try:
        x0 = float(bbox.get("x0", 0.0))
        y0 = float(bbox.get("y0", 0.0))
        x1 = float(bbox.get("x1", 0.0))
        y1 = float(bbox.get("y1", 0.0))
    except (TypeError, ValueError):
        return None

    if bbox_unit == "normalized_1000":
        x0, y0, x1, y1 = x0 / 1000.0, y0 / 1000.0, x1 / 1000.0, y1 / 1000.0
    elif bbox_unit != "normalized_1":
        if page is None:
            return None
        width = float(page.get("width") or 0)
        height = float(page.get("height") or 0)
        if width <= 0 or height <= 0:
            return None
        x0, y0, x1, y1 = x0 / width, y0 / height, x1 / width, y1 / height

    return {
        "x0": max(0.0, min(1.0, x0)),
        "y0": max(0.0, min(1.0, y0)),
        "x1": max(0.0, min(1.0, x1)),
        "y1": max(0.0, min(1.0, y1)),
    }


def _load_ir_payload(ir_path: str) -> dict | None:
    try:
        payload = json.loads(get_object_store().get_bytes(ir_path).decode("utf-8"))
    except (OSError, ValueError):
        logger.warning("Unreadable parsed IR at %s", ir_path)
        return None
    return payload if isinstance(payload, dict) else None


def delete_document(
    session_id: str,
    document_id: str,
    *,
    embedding: EmbeddingRuntime | None = None,
) -> None:
    """硬删除文档：数据库行 → 分块 → 磁盘产物 → 重建会话索引。

    索引重建失败时把当前快照置为 failed，宁可让用户重新索引，也不能让检索
    继续命中已删除的向量。
    """
    document = document_repo.get_document(document_id)
    if document is None or document["session_id"] != session_id:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        )

    _reject_if_job_running(session_id)

    chunk_repo.delete_chunks_for_document(document_id)
    document_repo.delete_document(document_id)
    _remove_document_files(document)

    try:
        if embedding is None:
            index_maintenance.refresh_after_document_change(session_id)
        else:
            index_maintenance.refresh_after_document_change(
                session_id, embedding=embedding
            )
    except Exception:
        logger.exception("Index rebuild failed after deleting document=%s", document_id)
        index_maintenance.invalidate_session_index(session_id, "索引重建失败")


def _reject_if_job_running(session_id: str) -> None:
    """删除 / 归档必须等摄取结束，否则 worker 会边写 chunk 边被删（FK 冲突）。"""
    if job_repo.has_running_job(session_id):
        raise JobInProgressError(
            "Session is still being processed, try again later.", session_id=session_id
        )


def _remove_document_files(document: DocumentRecord) -> None:
    store = get_object_store()
    for raw in (
        document.get("file_path"),
        document.get("parsed_markdown_path"),
        document.get("quality_report_path"),
    ):
        if raw:
            with suppress(OSError, ValueError):
                store.delete(raw)

    if document.get("parsed_ir_path"):
        with suppress(OSError, ValueError):
            store.delete_prefix(
                session_artifact_prefix(document["session_id"], document["id"])
            )
        ir_ref = str(document["parsed_ir_path"])
        if Path(ir_ref).is_absolute():
            artifact_dir = Path(ir_ref).resolve().parent
            root = data_dir().resolve()
            if artifact_dir != root and artifact_dir.is_relative_to(root):
                shutil.rmtree(artifact_dir, ignore_errors=True)
        else:
            with suppress(OSError, ValueError):
                store.delete_prefix(str(PurePosixPath(ir_ref).parent))


def list_library_documents(user_id: str | None) -> list[dict]:
    """文献库列表：跨会话、跨文档的统一视图。"""
    return [
        {
            "document_id": row["id"],
            "session_id": row["session_id"],
            "session_title": row["session_title"],
            "filename": row["filename"],
            "status": row["status"],
            "chunk_count": row["chunk_count"],
            "file_size": row["file_size"],
            "parse_quality_status": row["parse_quality_status"],
            "updated_at": row["updated_at"],
        }
        for row in document_repo.list_documents_with_session(user_id)
    ]


def get_document_content(session_id: str, document_id: str) -> dict:
    """Return the parsed body blocks of a document for the reader panel.

    Blocks keep their original ``id`` so a citation can scroll to the exact
    paragraph that produced it.
    """
    document = document_repo.get_document(document_id)
    if document is None or document["session_id"] != session_id:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}",
            session_id=session_id,
            document_id=document_id,
        )

    return {
        "document_id": document["id"],
        "filename": document["filename"],
        "status": document["status"],
        "parser_name": document["parser_name"],
        "parse_quality_status": document["parse_quality_status"],
        "chunk_count": document["chunk_count"],
        "blocks": _load_ir_blocks(document["parsed_ir_path"]),
    }


def _iter_ir_blocks(payload: dict) -> list[dict]:
    """IR 可能把 blocks 放在文档级，也可能只放在页级。"""
    blocks = payload.get("blocks") or []
    if blocks:
        return blocks
    return [block for page in payload.get("pages") or [] for block in page.get("blocks") or []]


def _load_ir_blocks(ir_path: str | None) -> list[dict]:
    """Flatten ``document.ir.json`` into ordered, renderable blocks."""
    if not ir_path:
        return []
    payload = _load_ir_payload(ir_path)
    if payload is None:
        return []

    raw_blocks = _iter_ir_blocks(payload)
    ordered = sorted(
        raw_blocks,
        key=lambda block: (
            block.get("page_number") or 0,
            block.get("reading_order") or 0,
            block.get("block_index") or 0,
        ),
    )
    pages = {page.get("page_number"): page for page in payload.get("pages") or []}
    bbox_unit = str(payload.get("bbox_unit") or "points")

    blocks: list[dict] = []
    for block in ordered:
        text = (block.get("text") or "").strip()
        block_type = block.get("type") or "unknown"
        if block_type == "header_footer":
            continue
        if not text and block_type not in {"formula", "figure"}:
            continue
        if block_type != "formula":
            # 旧解析产物里的行内公式可能没有 $ 分隔符，读取时补上
            text = wrap_bare_latex(text)
        page_number = block.get("page_number") or 0
        blocks.append(
            {
                "id": block.get("id") or "",
                "type": block_type,
                "text": text,
                "section_path": block.get("section_path") or [],
                "page_number": page_number,
                "bbox": _normalize_bbox(block.get("bbox"), pages.get(page_number), bbox_unit),
                "has_image": bool(block.get("has_image")),
            }
        )
    return blocks


def recover_orphaned_documents() -> None:
    """Scan for documents stuck in 'uploaded' status without a corresponding job and clean them up."""
    orphaned = document_repo.list_orphaned_uploaded_documents()
    for doc in orphaned:
        logger.warning(
            "Cleaning up orphaned document document_id=%s session_id=%s filename=%s",
            doc["id"], doc["session_id"], doc["filename"],
        )
        with suppress(RuntimeError, OSError):
            document_repo.delete_document(doc["id"])
        with suppress(OSError, ValueError):
            get_object_store().delete(doc["file_path"])
