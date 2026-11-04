"""MinerU Cloud API v4 parser backend.

Transport concerns live in ``mineru_client``; this module owns the result ZIP
contract and maps MinerU blocks into the project's ``RawParserResult``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import threading
import zipfile
from collections.abc import Callable
from typing import Any

from backend.config import settings
from backend.rag.ingestion.document_ir import BBoxUnit
from backend.rag.ingestion.mineru_client import (
    MinerUBatchFile,
    MinerUBatchNotFoundError,
    MinerUClient,
    MinerUClientConfig,
    MinerUError,
)
from backend.rag.ingestion.parser_backend import RawParserResult

logger = logging.getLogger(__name__)

# MinerU Cloud API limits
API_MAX_FILE_BYTES = 200 * 1024 * 1024  # 200 MB

_shared_client: MinerUClient | None = None
_shared_client_lock = threading.Lock()


def _build_shared_client() -> MinerUClient:
    return MinerUClient(
        MinerUClientConfig(
            base_url=settings.mineru_api_base_url,
            token=settings.mineru_api_key or "",
            request_timeout=float(settings.mineru_api_timeout),
            poll_interval=settings.mineru_api_poll_interval,
            poll_max_interval=settings.mineru_api_poll_max_interval,
            poll_timeout=float(settings.mineru_api_max_poll_time),
            max_retries=settings.mineru_api_max_retries,
            retry_base_delay=settings.mineru_api_retry_base_delay,
            retry_max_delay=settings.mineru_api_retry_max_delay,
            model_version=settings.mineru_model_version,
            language=settings.mineru_language,
            enable_formula=settings.mineru_formula_enable,
            enable_table=settings.mineru_table_enable,
            is_ocr=settings.mineru_api_is_ocr,
        )
    )


def _get_shared_client() -> MinerUClient:
    global _shared_client
    if _shared_client is not None:
        return _shared_client
    with _shared_client_lock:
        if _shared_client is None:
            _shared_client = _build_shared_client()
    return _shared_client


class MinerUApiBackend:
    name = "mineru_api"
    version = "1.1"

    def __init__(
        self,
        *,
        client: MinerUClient | None = None,
        document_id: str | None = None,
        resume_batch_id: str | None = None,
        on_batch_created: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._document_id = document_id
        self._resume_batch_id = resume_batch_id
        self._on_batch_created = on_batch_created

    def __repr__(self) -> str:
        return f"MinerUApiBackend(base_url={settings.mineru_api_base_url})"

    def parse(self, pdf_bytes: bytes, filename: str | None = None) -> RawParserResult:
        if len(pdf_bytes) > API_MAX_FILE_BYTES:
            raise MinerUError(
                f"PDF ({len(pdf_bytes)} bytes) exceeds MinerU API limit "
                f"({API_MAX_FILE_BYTES} bytes)"
            )

        client = self._client or _get_shared_client()
        safe_filename = filename or "document.pdf"
        data_id = self._document_id or hashlib.sha256(pdf_bytes).hexdigest()[:32]
        batch_file = MinerUBatchFile(
            filename=safe_filename,
            content=pdf_bytes,
            data_id=data_id,
            page_ranges=settings.mineru_api_page_ranges,
            is_ocr=settings.mineru_api_is_ocr,
        )

        logger.info(
            "MinerU API parse start filename=%s bytes=%d data_id=%s resume_batch=%s",
            safe_filename,
            len(pdf_bytes),
            data_id,
            self._resume_batch_id or "-",
        )
        result = self._resume(client, data_id, safe_filename)
        if result is None:
            result = self._submit(client, batch_file)

        state = str(result.get("state") or "")
        if state != "done":
            raise MinerUError(
                f"MinerU API task failed: state={state or 'unknown'}, "
                f"err_msg={result.get('err_msg', 'unknown')}"
            )
        result_url = result.get("full_zip_url")
        if not result_url:
            raise MinerUError("MinerU API task finished without full_zip_url")

        zip_bytes = client.download(str(result_url))
        parsed = parse_result_zip(zip_bytes)
        logger.info(
            "MinerU API parse succeeded filename=%s pages=%d bbox_unit=%s",
            safe_filename,
            parsed.page_count,
            parsed.bbox_unit,
        )
        return parsed

    def _resume(
        self,
        client: MinerUClient,
        data_id: str,
        filename: str,
    ) -> dict[str, Any] | None:
        if not self._resume_batch_id:
            return None
        try:
            results = client.wait(self._resume_batch_id)
        except MinerUBatchNotFoundError:
            logger.warning(
                "MinerU batch %s no longer exists; submitting a new batch",
                self._resume_batch_id,
            )
            return None

        result = _find_result(results, data_id, filename)
        if result is None:
            logger.warning(
                "MinerU batch %s has no result for data_id=%s; submitting again",
                self._resume_batch_id,
                data_id,
            )
            return None
        if result.get("state") == "failed":
            logger.warning(
                "MinerU batch %s failed for data_id=%s; submitting again: %s",
                self._resume_batch_id,
                data_id,
                result.get("err_msg"),
            )
            return None
        logger.info(
            "Resumed MinerU batch %s for data_id=%s state=%s",
            self._resume_batch_id,
            data_id,
            result.get("state"),
        )
        return result

    def _submit(
        self,
        client: MinerUClient,
        batch_file: MinerUBatchFile,
    ) -> dict[str, Any]:
        batch_id, urls = client.submit([batch_file])
        client.upload(urls[0], batch_file.content)
        if self._on_batch_created is not None:
            try:
                # Persist only after a successful upload: a failed upload would
                # otherwise leave a "waiting-file" batch that recovery must poll
                # for the whole timeout before resubmitting.
                self._on_batch_created(batch_id)
            except Exception:
                # Persisting the batch id improves recovery, but a local DB
                # hiccup must not prevent the already-created task from running.
                logger.exception("Failed to persist MinerU batch id %s", batch_id)

        results = client.wait(batch_id)
        result = _find_result(results, batch_file.data_id, batch_file.filename)
        if result is None:
            raise MinerUError(
                f"MinerU batch {batch_id} returned no result for "
                f"data_id={batch_file.data_id}"
            )
        return result


def _find_result(
    results: list[dict[str, Any]],
    data_id: str,
    filename: str,
) -> dict[str, Any] | None:
    for item in results:
        if str(item.get("data_id") or "") == data_id:
            return item
    for item in results:
        if str(item.get("file_name") or "") == filename:
            return item
    return None


def parse_result_zip(raw: bytes) -> RawParserResult:
    """Parse a MinerU result ZIP into ``RawParserResult``.

    The ZIP is never extracted to disk; only known members are read, avoiding
    path traversal and accidental writes.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            full_md = (
                zf.read("full.md").decode("utf-8", errors="replace")
                if "full.md" in names
                else ""
            )
            pages, bbox_unit = _parse_zip_content(zf, names)
    except zipfile.BadZipFile as exc:
        raise MinerUError("MinerU result is not a valid ZIP archive") from exc

    if not pages and not full_md.strip():
        raise MinerUError("MinerU result ZIP contains no parseable content")

    return RawParserResult(
        markdown=full_md,
        page_count=len(pages),
        pages=pages,
        metadata={"source": "mineru_api"},
        source_parser=MinerUApiBackend.name,
        bbox_unit=bbox_unit,
    )


def _parse_zip_content(
    zf: zipfile.ZipFile,
    names: list[str],
) -> tuple[list[dict[str, Any]], BBoxUnit]:
    page_sizes: dict[int, tuple[float, float]] = {}
    if "layout.json" in names:
        try:
            layout = json.loads(zf.read("layout.json"))
            for page_info in layout.get("pdf_info", []):
                idx = page_info.get("page_idx")
                size = page_info.get("page_size")
                if idx is not None and isinstance(size, (list, tuple)) and len(size) >= 2:
                    page_sizes[int(idx)] = (float(size[0]), float(size[1]))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse layout.json: %s", exc)

    cl_v2_name = next((n for n in names if "content_list_v2.json" in n), None)
    if cl_v2_name:
        try:
            data = json.loads(zf.read(cl_v2_name))
            if not isinstance(data, list):
                raise ValueError("content_list_v2 is not an array")
            return _map_pages_from_cl_v2(data, page_sizes), "normalized_1000"
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse %s, falling back: %s", cl_v2_name, exc)

    cl_v1_name = next((n for n in names if "content_list.json" in n and "v2" not in n), None)
    if cl_v1_name:
        try:
            data = json.loads(zf.read(cl_v1_name))
            if not isinstance(data, list):
                raise ValueError("content_list is not an array")
            return _map_pages_from_cl_v1(data, page_sizes), "normalized_1000"
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse %s, falling back: %s", cl_v1_name, exc)

    if "content.json" in names:
        try:
            content = json.loads(zf.read("content.json"))
            return _map_pages(content, page_sizes), "points"
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse content.json: %s", exc)

    logger.warning("No parseable content file found in result ZIP")
    return [], "points"


def _map_pages_from_cl_v2(
    data: list[list[dict[str, Any]]],
    page_sizes: dict[int, tuple[float, float]],
) -> list[dict[str, Any]]:
    """Map ``content_list_v2.json`` (page-grouped array) to page dicts."""
    pages: list[dict[str, Any]] = []
    for page_idx, page_items in enumerate(data):
        width, height = page_sizes.get(page_idx, (0.0, 0.0))
        blocks: list[dict[str, Any]] = []
        for item in page_items:
            mapped = _map_block_from_v2(item)
            if mapped is not None:
                blocks.append(mapped)
        pages.append(
            {
                "page_number": page_idx + 1,
                "width": width,
                "height": height,
                "blocks": blocks,
            }
        )
    return pages


def _map_pages_from_cl_v1(
    data: list[dict[str, Any]],
    page_sizes: dict[int, tuple[float, float]],
) -> list[dict[str, Any]]:
    """Map ``content_list.json`` (flat array) to page dicts."""
    page_map: dict[int, list[dict[str, Any]]] = {}
    for item in data:
        page_idx = int(item.get("page_idx", 0))
        mapped = _map_block_from_v1(item)
        if mapped is not None:
            page_map.setdefault(page_idx, []).append(mapped)

    if not page_map:
        return []

    max_page = max(page_map)
    pages: list[dict[str, Any]] = []
    for i in range(max_page + 1):
        width, height = page_sizes.get(i, (0.0, 0.0))
        pages.append(
            {
                "page_number": i + 1,
                "width": width,
                "height": height,
                "blocks": page_map.get(i, []),
            }
        )
    return pages


def _map_pages(
    content: dict[str, Any],
    page_sizes: dict[int, tuple[float, float]],
) -> list[dict[str, Any]]:
    """Map legacy ``content.json`` pages; legacy bboxes are PDF points."""
    pages: list[dict[str, Any]] = []
    for i, page_data in enumerate(content.get("pages", [])):
        page_number = int(page_data.get("page_number", i + 1))
        width, height = page_sizes.get(
            i,
            (float(page_data.get("width", 0.0)), float(page_data.get("height", 0.0))),
        )
        raw_blocks: list[dict[str, Any]] = (
            page_data.get("page_blocks") or page_data.get("blocks") or []
        )
        pages.append(
            {
                "page_number": page_number,
                "width": width,
                "height": height,
                "blocks": [_map_block(block) for block in raw_blocks],
            }
        )
    return pages


def _map_block(block: dict[str, Any]) -> dict[str, Any]:
    """Map a legacy ``content.json`` block to the normalizer format."""
    mapped: dict[str, Any] = {
        "type": block.get("type", "paragraph"),
        "text": block.get("text", ""),
        "bbox": block.get("bbox", [0.0, 0.0, 0.0, 0.0]),
    }
    if "confidence" in block:
        mapped["confidence"] = block["confidence"]
    if block.get("links"):
        mapped["links"] = block["links"]
    return mapped


def _concat_fragments(fragments: list[Any]) -> str:
    """Concatenate MinerU content fragments into plain text."""
    parts: list[str] = []
    if isinstance(fragments, list):
        for fragment in fragments:
            if isinstance(fragment, str):
                if fragment:
                    parts.append(fragment)
                continue
            if isinstance(fragment, dict):
                text = fragment.get("content", "")
                if text:
                    parts.append(str(text))
                children = fragment.get("children")
                if children:
                    parts.append(_concat_fragments(children))
    return "".join(parts)


_V2_TYPE_MAP: dict[str, str] = {
    "title": "title",
    "paragraph": "paragraph",
    "equation_interline": "formula",
    "page_footnote": "footnote",
    "page_aside_text": "aside_text",
}


def _map_block_from_v2(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map a ``content_list_v2.json`` block to the normalizer format."""
    if not isinstance(item, dict):
        return None
    raw_type = item.get("type", "")
    norm_type = _V2_TYPE_MAP.get(raw_type, raw_type)
    bbox = item.get("bbox", [0.0, 0.0, 0.0, 0.0])
    content = item.get("content", {})
    if not isinstance(content, dict):
        content = {}

    text = ""
    if raw_type == "title":
        text = _concat_fragments(content.get("title_content", []))
    elif raw_type == "paragraph":
        text = _concat_fragments(content.get("paragraph_content", []))
    elif raw_type == "equation_interline":
        text = str(content.get("math_content", "") or "")
    elif raw_type == "image":
        captions = content.get("image_caption", [])
        text = _concat_fragments(captions)
        if not text:
            return None
        norm_type = "figure_caption"
    elif raw_type == "chart":
        captions = content.get("chart_caption", [])
        text = _concat_fragments(captions)
        if not text:
            return None
        norm_type = "figure_caption"
    elif raw_type == "table":
        # table_body is the actual table in HTML; keeping only captions loses
        # the content that table-oriented questions need.
        caption = _concat_fragments(content.get("table_caption", []))
        body = str(content.get("table_body", "") or "")
        footnote = _concat_fragments(content.get("table_footnote", []))
        text = "\n\n".join(
            part.strip() for part in (caption, body, footnote) if part and part.strip()
        )
        norm_type = "table"
    elif raw_type == "list":
        items = content.get("list_items", [])
        texts: list[str] = []
        for item_data in items:
            if isinstance(item_data, dict):
                item_text = _concat_fragments(item_data.get("item_content", []))
                if item_text:
                    texts.append(item_text)
        text = "\n".join(texts)
        norm_type = "paragraph"
    elif raw_type == "page_aside_text":
        text = _concat_fragments(content.get("page_aside_text_content", []))
    elif raw_type == "page_footnote":
        text = _concat_fragments(content.get("page_footnote_content", []))

    text = text.strip()
    if not text:
        return None

    return {
        "type": norm_type,
        "text": text,
        "bbox": bbox,
    }


def _map_block_from_v1(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map a ``content_list.json`` (v1) block to the normalizer format."""
    raw_type = item.get("type", "")
    text = str(item.get("text", "")).strip()
    bbox = item.get("bbox", [0.0, 0.0, 0.0, 0.0])

    if raw_type == "text":
        text_level = item.get("text_level", 0)
        norm_type = "title" if text_level >= 1 else "paragraph"
    elif raw_type == "equation":
        norm_type = "formula"
    elif raw_type == "table":
        norm_type = "table"
        caption = _concat_fragments(item.get("table_caption", []))
        body = str(item.get("table_body") or text)
        footnote = _concat_fragments(item.get("table_footnote", []))
        text = "\n\n".join(
            part.strip() for part in (caption, body, footnote) if part and part.strip()
        )
    elif raw_type in {"image", "chart"}:
        norm_type = "figure_caption"
        text = _concat_fragments(item.get(f"{raw_type}_caption", []))
    elif raw_type in {"aside_text", "page_footnote"}:
        norm_type = "footnote"
    else:
        norm_type = raw_type

    if not text and norm_type not in {"formula", "table"}:
        return None

    return {
        "type": norm_type,
        "text": text,
        "bbox": bbox,
    }
