"""SSE framing: application events -> transport models -> ``data:`` frames.

Keep-alive and disconnect handling are delegated to
``sse_starlette.EventSourceResponse``; this module only owns the wire format and
the thin transport wrapper.
"""

import asyncio
import logging
from collections.abc import AsyncIterator

from sse_starlette import EventSourceResponse

from backend.api.schemas.chat import (
    ChatStreamDoneEvent,
    ChatStreamErrorEvent,
    ChatStreamEvent,
    ChatStreamRunStartedEvent,
    ChatStreamSourcesEvent,
    ChatStreamStatusEvent,
    ChatStreamTokenEvent,
    ChatStreamToolCallEvent,
    ChatStreamToolResultEvent,
    ChatStreamWarningEvent,
    RunStartedValue,
    ToolCallValue,
    ToolResultValue,
)
from backend.application.conversation.events import (
    ChatEvent,
    DoneEvent,
    ErrorEvent,
    RunStartedEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
    WarningEvent,
)


logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = 15.0


def build_stream_response(
    events: AsyncIterator[ChatEvent], *, session_id: str = ""
) -> EventSourceResponse:
    """Wrap the domain event stream in the SSE transport.

    Keep-alive pings and client-disconnect detection come from
    ``EventSourceResponse``; this wrapper only maps events and shields the
    stream from unexpected failures.
    """

    async def frames() -> AsyncIterator[bytes]:
        try:
            async for frame in sse_frames(events):
                yield frame
        except asyncio.CancelledError:
            logger.info("SSE stream cancelled by client session=%s", session_id)
            return
        except Exception:
            logger.exception("Unhandled error in SSE stream session=%s", session_id)
            yield encode_sse_event(ErrorEvent(value="internal_error")).encode("utf-8")
            yield encode_sse_event(DoneEvent()).encode("utf-8")

    return EventSourceResponse(
        frames(),
        ping=HEARTBEAT_INTERVAL_SECONDS,
        headers={
            "Cache-Control": "no-cache",
            # nginx 默认缓冲会让流式退化成「等全部生成完再吐」，必须显式关闭
            "X-Accel-Buffering": "no",
        },
    )


async def sse_frames(events: AsyncIterator[ChatEvent]) -> AsyncIterator[bytes]:
    """Encode domain events as complete SSE frames.

    Frames are emitted as ``bytes`` so the transport sends them verbatim instead
    of re-wrapping them in another ``data:`` line.
    """
    async for event in events:
        yield encode_sse_event(event).encode("utf-8")


def encode_sse_event(event: ChatEvent) -> str:
    return f"data: {to_transport_event(event).model_dump_json()}\n\n"


def to_transport_event(event: ChatEvent) -> ChatStreamEvent:
    if isinstance(event, StatusEvent):
        return ChatStreamStatusEvent(type="status", value=event.value)
    if isinstance(event, RunStartedEvent):
        return ChatStreamRunStartedEvent(
            type="run_started",
            value=RunStartedValue(run_id=event.run_id, max_steps=event.max_steps),
        )
    if isinstance(event, ToolCallEvent):
        return ChatStreamToolCallEvent(
            type="tool_call",
            value=ToolCallValue(
                run_id=event.run_id,
                step=event.step,
                tool=event.tool,
                arguments=event.arguments,
            ),
        )
    if isinstance(event, ToolResultEvent):
        return ChatStreamToolResultEvent(
            type="tool_result",
            value=ToolResultValue(
                run_id=event.run_id,
                step=event.step,
                tool=event.tool,
                status=event.status,
                summary=event.summary,
                sources=event.sources,
            ),
        )
    if isinstance(event, TokenEvent):
        return ChatStreamTokenEvent(type="token", value=event.value)
    if isinstance(event, SourcesEvent):
        return ChatStreamSourcesEvent(type="sources", value=event.value)
    if isinstance(event, WarningEvent):
        return ChatStreamWarningEvent(type="warning", value=event.value)
    if isinstance(event, ErrorEvent):
        return ChatStreamErrorEvent(type="error", value=event.value)
    if isinstance(event, DoneEvent):
        return ChatStreamDoneEvent(type="done", run_id=event.run_id)
    raise TypeError(f"Unsupported chat event: {type(event).__name__}")
