"""Per-user embedding runtime caching and index compatibility checks."""

from typing import Any, cast

import pytest

from backend import composition
from backend.application.model_settings import service
from backend.application.model_settings.service import ResolvedEmbedding


def _resolved(**overrides: Any) -> ResolvedEmbedding:
    values: dict[str, Any] = {
        "mode": "remote",
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "sk-test",
        "dim": 1024,
        "key_source": "user",
    }
    values.update(overrides)
    return ResolvedEmbedding(**values)


@pytest.mark.unit
def test_user_embedding_is_cached_by_fingerprint_and_key(monkeypatch):
    resolved = _resolved()
    monkeypatch.setattr(
        "backend.application.model_settings.service.resolve_embedding",
        lambda user_id: resolved,
    )
    composition._user_embeddings.clear()

    first = composition.user_embedding("u1")
    second = composition.user_embedding("u1")
    assert first is second
    assert first.fingerprint == "remote|siliconflow|BAAI/bge-m3|1024"

    rotated = _resolved(api_key="sk-rotated")
    monkeypatch.setattr(
        "backend.application.model_settings.service.resolve_embedding",
        lambda user_id: rotated,
    )
    third = composition.user_embedding("u1")
    assert third is not first
    assert third.fingerprint == first.fingerprint


@pytest.mark.unit
def test_index_embedding_status_compares_fingerprints(monkeypatch):
    monkeypatch.setattr(
        service,
        "resolve_embedding",
        lambda user_id: _resolved(),
    )
    monkeypatch.setattr(service, "env_embedding_fingerprint", lambda: "env|legacy")

    snapshot = cast(
        Any,
        {
            "embedding_fingerprint": "remote|siliconflow|BAAI/bge-m3|1024",
            "embedding_model": "BAAI/bge-m3",
        },
    )
    status = service.index_embedding_status(snapshot, "u1")
    assert status["stale"] is False
    assert status["current_model"] == "BAAI/bge-m3"

    stale_snapshot = cast(
        Any,
        {
            "embedding_fingerprint": "remote|siliconflow|old-model|768",
            "embedding_model": "old-model",
        },
    )
    stale = service.index_embedding_status(stale_snapshot, "u1")
    assert stale["stale"] is True
    assert stale["index_model"] == "old-model"

    legacy = cast(Any, {"embedding_fingerprint": None, "embedding_model": None})
    assert service.index_embedding_status(legacy, "u1")["stale"] is True
