import logging

from fastapi import APIRouter, Depends
from sse_starlette import EventSourceResponse

from backend.api.deps import (
    get_accessible_session,
    get_text_completer,
    get_user_embedding,
    get_user_reranker,
)
from backend.api.schemas import ChatMessage
from backend.api.security import get_current_user
from backend.api.streaming import build_stream_response
from backend.application.conversation.chat import stream_session_chat
from backend.domain.ports import EmbeddingRuntime, Reranker, TextCompleter

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sessions/{session_id}/messages")
async def chat(
    session_id: str,
    message: ChatMessage,
    session: dict = Depends(get_accessible_session),
    user: dict = Depends(get_current_user),
    completer: TextCompleter = Depends(get_text_completer),
    embedding: EmbeddingRuntime = Depends(get_user_embedding),
    reranker: Reranker | None = Depends(get_user_reranker),
) -> EventSourceResponse:
    """发送提问，以 text/event-stream 流式返回回答。"""
    runner = None
    if message.mode == "agent":
        from backend.composition import agent_runner

        runner = agent_runner()
    events = stream_session_chat(
        session_id=session["id"],
        content=message.content,
        user_id=user.get("id"),
        regenerate=message.regenerate,
        client_message_id=message.client_message_id,
        completer=completer,
        embedding=embedding,
        reranker=reranker,
        mode=message.mode,
        agent_runner=runner,
    )
    return build_stream_response(events, session_id=session["id"])
