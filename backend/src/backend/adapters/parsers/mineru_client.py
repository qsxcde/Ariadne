"""HTTP client for MinerU Open API v4.

The authenticated API client talks to ``mineru.net``; signed-URL uploads and
CDN downloads deliberately use a separate client without the bearer token.
No ``backend.config`` import here: the adapter passes configuration explicitly
so the transport can be unit-tested without the settings singleton.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import RetryCallState, Retrying, retry_if_exception_type, stop_after_attempt

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
_TERMINAL_STATES = frozenset({"done", "failed"})
_TASK_NOT_FOUND_CODES = frozenset({"-60012"})
_PERMANENT_API_CODES = frozenset({"-60005", "-60006", "A0202", "A0211"})


class MinerUError(RuntimeError):
    """Base error with enough metadata for the ingestion layer to classify it."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float = 0.0,
        code: object = None,
        trace_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after
        self.code = code
        self.trace_id = trace_id


class MinerURetryableError(MinerUError):
    def __init__(self, message: str, *, retry_after: float = 0.0) -> None:
        super().__init__(message, retryable=True, retry_after=retry_after)


class MinerUPermanentError(MinerUError):
    pass


class MinerUBatchNotFoundError(MinerUPermanentError):
    pass


class _TransportFailure(Exception):
    """Internal marker so tenacity can retry raw httpx transport failures."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(str(cause))
        self.cause = cause


@dataclass(frozen=True)
class MinerUClientConfig:
    base_url: str
    token: str
    request_timeout: float = 300.0
    poll_interval: float = 2.0
    poll_max_interval: float = 10.0
    poll_timeout: float = 600.0
    max_retries: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 30.0
    model_version: str = "vlm"
    language: str = "ch"
    enable_formula: bool = True
    enable_table: bool = True
    is_ocr: bool = False


@dataclass(frozen=True)
class MinerUBatchFile:
    filename: str
    content: bytes
    data_id: str
    page_ranges: str | None = None
    is_ocr: bool | None = None


class MinerUClient:
    """Synchronous client for the batch upload + polling workflow."""

    def __init__(
        self,
        config: MinerUClientConfig,
        *,
        api_client: httpx.Client | None = None,
        plain_client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        api_base = config.base_url.rstrip("/")
        if not api_base.endswith("/api/v4"):
            api_base = f"{api_base}/api/v4"
        self._api = api_client or httpx.Client(
            base_url=api_base,
            headers={"Authorization": f"Bearer {config.token}"},
            timeout=httpx.Timeout(
                connect=10.0,
                read=60.0,
                write=config.request_timeout,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=True,
        )
        self._plain = plain_client or httpx.Client(
            timeout=httpx.Timeout(
                connect=10.0,
                read=config.request_timeout,
                write=config.request_timeout,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=True,
        )

    def close(self) -> None:
        self._api.close()
        self._plain.close()

    def submit(
        self,
        files: list[MinerUBatchFile],
        *,
        model_version: str | None = None,
        language: str | None = None,
        enable_formula: bool | None = None,
        enable_table: bool | None = None,
    ) -> tuple[str, list[str]]:
        if not files:
            raise ValueError("MinerU batch must contain at least one file")

        config = self.config
        payload: dict[str, object] = {
            "files": [self._file_payload(item) for item in files],
            "model_version": model_version or config.model_version,
            "enable_formula": (
                config.enable_formula if enable_formula is None else enable_formula
            ),
            "enable_table": config.enable_table if enable_table is None else enable_table,
            "language": language or config.language,
        }
        # POST is not idempotent: retrying a read timeout could create another
        # batch and double-bill. The job runner can retry the whole ingestion.
        response = self._api_request("POST", "/file-urls/batch", json=payload, retries=0)
        body = _decode_json(response)
        _raise_for_api_code(body, "submit")

        data = body.get("data") or {}
        batch_id = data.get("batch_id")
        urls = data.get("file_urls") or []
        if not batch_id or len(urls) != len(files):
            raise MinerUError(
                "MinerU submit response is missing batch_id/file_urls",
                trace_id=_trace_id(body),
            )
        return str(batch_id), [str(url) for url in urls]

    def upload(self, signed_url: str, content: bytes) -> None:
        """Upload bytes to the signed URL; never send Authorization/Content-Type."""
        self._plain_request("PUT", signed_url, content=content)

    def wait(self, batch_id: str, *, timeout: float | None = None) -> list[dict[str, Any]]:
        deadline = time.monotonic() + (
            self.config.poll_timeout if timeout is None else timeout
        )
        interval = max(0.0, self.config.poll_interval)
        last_signature: tuple[str, ...] | None = None

        while True:
            response = self._api_request("GET", f"/extract-results/batch/{batch_id}")
            body = _decode_json(response)
            _raise_for_api_code(body, "poll")
            results = (body.get("data") or {}).get("extract_result") or []
            states = [str(item.get("state") or "") for item in results]
            progress = [
                _progress_summary(item.get("extract_progress")) for item in results
            ]
            signature = tuple(states + progress)
            if results and signature != last_signature:
                logger.info(
                    "MinerU batch %s states=%s progress=%s",
                    batch_id,
                    states,
                    progress,
                )
                last_signature = signature
            if results and all(state in _TERMINAL_STATES for state in states):
                return results

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MinerUError(
                    f"MinerU batch {batch_id} did not finish within "
                    f"{self.config.poll_timeout:.0f}s"
                )
            time.sleep(min(interval, remaining))
            interval = min(
                max(interval * 1.5, 0.05),
                self.config.poll_max_interval,
            )

    def download(self, result_url: str) -> bytes:
        response = self._plain_request("GET", result_url)
        return response.content

    def _file_payload(self, item: MinerUBatchFile) -> dict[str, object]:
        payload: dict[str, object] = {
            "name": item.filename,
            "data_id": item.data_id,
            "is_ocr": self.config.is_ocr if item.is_ocr is None else item.is_ocr,
        }
        if item.page_ranges:
            payload["page_ranges"] = item.page_ranges
        return payload

    def _api_request(
        self,
        method: str,
        url: str,
        *,
        retries: int | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._request(
            self._api, method, url, retries=retries, authenticated=True, **kwargs
        )

    def _plain_request(
        self,
        method: str,
        url: str,
        *,
        retries: int | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        return self._request(
            self._plain, method, url, retries=retries, authenticated=False, **kwargs
        )

    def _request(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        retries: int | None = None,
        authenticated: bool,
        **kwargs: Any,
    ) -> httpx.Response:
        """One retry loop; the two transports differ only in client and prefix."""
        attempts = self.config.max_retries if retries is None else max(0, retries)
        prefix = "MinerU" if authenticated else "MinerU signed URL"

        def send() -> httpx.Response:
            try:
                response = client.request(method, url, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                raise _TransportFailure(exc) from exc

            if response.status_code in _RETRYABLE_STATUS:
                raise MinerURetryableError(
                    f"{prefix} HTTP {response.status_code} for {method} {url}: "
                    f"{response.text[:200]}",
                    retry_after=_retry_after_seconds(response),
                )
            if authenticated and response.status_code in {401, 403}:
                raise MinerUPermanentError(
                    f"MinerU authentication failed (HTTP {response.status_code})"
                )
            if response.is_success:
                return response
            raise MinerUPermanentError(
                f"{prefix} HTTP {response.status_code} for {method} {url}: "
                f"{response.text[:200]}"
            )

        retrying = Retrying(
            stop=stop_after_attempt(attempts + 1),
            retry=retry_if_exception_type((_TransportFailure, MinerURetryableError)),
            wait=self._retry_delay,
            before_sleep=lambda state: self._log_retry(state, method, url),
            reraise=True,
        )
        try:
            return retrying(send)
        except _TransportFailure as exc:
            raise MinerUError(
                f"{prefix} request failed after {attempts + 1} attempt(s): {method} {url}"
            ) from exc.cause
        except MinerURetryableError as exc:
            raise MinerUError(
                f"{prefix} request failed after {attempts + 1} attempt(s): {method} {url}"
            ) from exc

    def _retry_delay(self, retry_state: RetryCallState) -> float:
        """Honour ``Retry-After`` when present, else exponential backoff plus jitter."""
        error = retry_state.outcome.exception() if retry_state.outcome else None
        retry_after = float(getattr(error, "retry_after", 0.0) or 0.0)
        if retry_after > 0:
            return min(retry_after, self.config.retry_max_delay)
        exponent = max(0, retry_state.attempt_number - 1)
        delay = min(
            self.config.retry_base_delay * (2**exponent),
            self.config.retry_max_delay,
        )
        return delay + random.uniform(0.0, 0.25)

    def _log_retry(self, retry_state: RetryCallState, method: str, url: str) -> None:
        error = retry_state.outcome.exception() if retry_state.outcome else None
        action = retry_state.next_action
        logger.warning(
            "MinerU %s %s failed (attempt %d), retrying in %.2fs: %s",
            method,
            url,
            retry_state.attempt_number,
            action.sleep if action else 0.0,
            error,
        )


def _decode_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise MinerUError("MinerU returned a non-JSON response") from exc
    if not isinstance(payload, dict):
        raise MinerUError("MinerU returned an unexpected JSON payload")
    return payload


def _raise_for_api_code(body: dict[str, Any], stage: str) -> None:
    code = body.get("code")
    if code == 0:
        return
    code_text = str(code)
    message = (
        f"MinerU API error at {stage}: code={code}, "
        f"msg={body.get('msg', 'unknown')}, trace_id={_trace_id(body)}"
    )
    if code_text in _TASK_NOT_FOUND_CODES:
        raise MinerUBatchNotFoundError(message)
    if code_text in _PERMANENT_API_CODES:
        raise MinerUPermanentError(message)
    raise MinerUPermanentError(message)


def _trace_id(body: dict[str, Any]) -> str | None:
    value = body.get("trace_id")
    return str(value) if value else None


def _retry_after_seconds(response: httpx.Response) -> float:
    value = response.headers.get("Retry-After")
    if not value:
        return 0.0
    try:
        return max(0.0, float(value))
    except ValueError:
        return 0.0


def _progress_summary(progress: object) -> str:
    if not isinstance(progress, dict):
        return "-"
    extracted = progress.get("extracted_pages")
    total = progress.get("total_pages")
    if extracted is None and total is None:
        return "-"
    return f"{extracted or 0}/{total or '?'}"
