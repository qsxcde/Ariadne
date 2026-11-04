"""SSE framing: domain events to wire frames."""

import json

import pytest

from backend.api.streaming import (
    HEARTBEAT_INTERVAL_SECONDS,
    build_stream_response,
    encode_sse_event,
    sse_frames,
    to_transport_event,
)
from backend.application.conversation.events import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    WarningEvent,
)
from backend.domain.models import SourceRef


@pytest.mark.unit
@pytest.mark.parametrize(
    ("event", "expected_type"),
    [
        (StatusEvent(value="retrieving"), "status"),
        (TokenEvent(value="hi"), "token"),
        (SourcesEvent(value=[]), "sources"),
        (WarningEvent(value="careful"), "warning"),
        (ErrorEvent(value="boom"), "error"),
        (DoneEvent(), "done"),
    ],
)
def test_every_domain_event_maps_to_one_wire_type(event, expected_type):
    transport = to_transport_event(event)

    assert transport.type == expected_type


@pytest.mark.unit
def test_unknown_domain_event_fails_loudly():
    with pytest.raises(TypeError):
        to_transport_event(object())  # type: ignore[arg-type]


@pytest.mark.unit
def test_frame_is_valid_json_with_the_sse_data_prefix():
    frame = encode_sse_event(
        SourcesEvent(
            value=[SourceRef(section="Intro", chunk_index=2, text_excerpt="quote")]
        )
    )

    assert frame.startswith("data: " )
    assert frame.endswith("\n\n")
    payload = json.loads(frame[len("data: "):].strip())
    assert payload["type"] == "sources"
    assert payload["value"][0]["section"] == "Intro"


@pytest.mark.unit
async def test_frames_are_bytes_with_the_sse_data_prefix():
    async def _events():
        yield TokenEvent(value="first")
        yield DoneEvent()

    frames = [frame async for frame in sse_frames(_events())]

    assert len(frames) == 2
    assert all(isinstance(frame, bytes) for frame in frames)
    assert frames[0].startswith(b"data: ")
    assert frames[0].endswith(b"\n\n")
    assert json.loads(frames[0][len(b"data: "):].strip())["value"] == "first"


@pytest.mark.unit
async def test_frames_forward_upstream_errors():
    async def _failing_events():
        raise RuntimeError("upstream broke")
        yield DoneEvent()  # pragma: no cover - unreachable

    with pytest.raises(RuntimeError, match="upstream broke"):
        async for _ in sse_frames(_failing_events()):
            pass


@pytest.mark.unit
def test_stream_response_delegates_keep_alive_to_the_transport():
    async def _events():
        yield DoneEvent()

    response = build_stream_response(_events(), session_id="s1")

    assert response.ping_interval == HEARTBEAT_INTERVAL_SECONDS
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
