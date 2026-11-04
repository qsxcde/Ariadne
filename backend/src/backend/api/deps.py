"""Reusable FastAPI dependencies (authorization lives here, once)."""

from fastapi import Depends

from backend.api.security import get_current_user
from backend.application.conversation import sessions as session_service
from backend.composition import user_embedding, user_reranker, user_text_completer
from backend.domain.exceptions import SessionNotFoundError
from backend.domain.ports import EmbeddingRuntime, Reranker, TextCompleter


def get_text_completer(
    user: dict = Depends(get_current_user),
) -> TextCompleter:
    """Wire the caller's LLM (user key first, env fallback) at the transport edge."""
    return user_text_completer(user.get("id") or None)


def get_user_embedding(
    user: dict = Depends(get_current_user),
) -> EmbeddingRuntime:
    """Wire the caller's embedder at the transport edge."""
    return user_embedding(user.get("id") or None)


def get_user_reranker(
    user: dict = Depends(get_current_user),
) -> Reranker | None:
    """Wire the caller's reranker; None means reranking is disabled."""
    return user_reranker(user.get("id") or None)


def get_accessible_session(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Resolve a session the caller may access, or fail with a domain error.

    Keeping this in one dependency guarantees that every route applies the same
    ownership rule and that the 404 response is produced by a single handler.
    """
    session = session_service.get_accessible_session(session_id, user.get("id"))
    if session is None:
        raise SessionNotFoundError(f"Session not found: {session_id}", session_id=session_id)
    return session
