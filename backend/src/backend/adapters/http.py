"""Shared outbound HTTP GET: one connection pool and one retry policy.

Application services fetch arXiv, Crossref, feed and landing pages; they all go
through here so redirects, user agents and backoff behaviour stay identical.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from backend.adapters.resources import LazyResource

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0
DEFAULT_USER_AGENT = "Ariadne/0.1"
MAX_ATTEMPTS = 3
_BACKOFF_MULTIPLIER = 0.5
_BACKOFF_MAX = 10.0


def _build_client() -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": DEFAULT_USER_AGENT},
        limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
    )


_client: LazyResource[httpx.Client] = LazyResource(_build_client)


def is_retryable(error: BaseException) -> bool:
    """Transport failures and server-side errors are worth another attempt."""
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code >= 500
    return isinstance(error, httpx.HTTPError)


def build_retrying(*, wait: Any | None = None) -> Retrying:
    """Retry policy shared by every outbound call.

    ``wait`` is injectable so tests can run the same policy without sleeping.
    """
    return Retrying(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        retry=retry_if_exception(is_retryable),
        wait=(
            wait
            if wait is not None
            else wait_exponential(multiplier=_BACKOFF_MULTIPLIER, max=_BACKOFF_MAX)
        ),
        reraise=True,
    )


_retrying = build_retrying()


def get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    headers: dict[str, str] | None = None,
    user_agent: str | None = None,
) -> httpx.Response:
    """GET ``url`` through the shared pool, raising the last ``httpx.HTTPError``.

    Callers keep their own domain-level error mapping; this layer only owns
    transport, redirects and backoff.
    """

    def send() -> httpx.Response:
        request_headers = dict(headers or {})
        if user_agent:
            request_headers["User-Agent"] = user_agent
        response = _client.get().get(
            url,
            params=params,
            timeout=timeout,
            headers=request_headers or None,
        )
        response.raise_for_status()
        return response

    return _retrying(send)
