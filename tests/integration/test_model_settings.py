"""Per-user model settings: storage, encryption, precedence and API."""

import pytest
from fastapi.testclient import TestClient

from backend.api.security import get_current_user
from backend.application.model_settings import service
from backend.config import settings
from backend.main import app
from backend.storage.sqlite import model_settings as model_settings_repo


@pytest.fixture(autouse=True)
def _model_settings_env(monkeypatch):
    monkeypatch.setattr(settings, "deepseek_api_key", "env-deepseek-key")
    monkeypatch.setattr(settings, "deepseek_base_url", "https://api.deepseek.com")
    monkeypatch.setattr(settings, "jwt_secret_key", "test-model-settings-secret")
    monkeypatch.setattr(settings, "embedding_remote_api_key", "env-embedding-key")
    monkeypatch.setattr(settings, "embedding_remote_model", "BAAI/bge-m3")
    monkeypatch.setattr(
        settings, "embedding_remote_base_url", "https://api.siliconflow.cn/v1"
    )
    monkeypatch.setattr(
        settings, "reranker_remote_model", "BAAI/bge-reranker-v2-m3"
    )
    monkeypatch.setattr(
        settings, "reranker_remote_base_url", "https://api.siliconflow.cn/v1"
    )


@pytest.mark.integration
def test_user_key_is_encrypted_and_wins():
    view = service.update_settings(
        "u1",
        {
            "llm_provider": "deepseek",
            "llm_model": "deepseek-v4-pro",
            "llm_api_key": "sk-user-12345678",
        },
    )

    row = model_settings_repo.get("u1")
    assert row is not None
    assert row["llm_api_key"].startswith("enc:v1:")
    assert "sk-user-12345678" not in row["llm_api_key"]
    assert view["llm"]["api_key_hint"] == "••••5678"
    assert view["llm"]["key_source"] == "user"

    resolved = service.resolve_llm("u1")
    assert resolved.model == "deepseek-v4-pro"
    assert resolved.api_key == "sk-user-12345678"
    assert resolved.key_source == "user"


@pytest.mark.integration
def test_clearing_user_key_falls_back_to_env():
    service.update_settings("u1", {"llm_api_key": "sk-user-12345678"})
    view = service.update_settings("u1", {"llm_api_key": ""})

    assert view["llm"]["key_source"] == "env"
    assert view["llm"]["api_key_hint"] is None
    resolved = service.resolve_llm("u1")
    assert resolved.api_key == "env-deepseek-key"
    assert resolved.key_source == "env"


@pytest.mark.integration
def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="Unsupported LLM model"):
        service.update_settings("u1", {"llm_model": "not-a-model"})


@pytest.mark.integration
def test_settings_are_scoped_per_user():
    service.update_settings("u1", {"llm_model": "deepseek-v4-pro"})
    service.update_settings("u2", {"llm_model": "deepseek-flash"})

    assert service.get_settings("u1")["llm"]["model"] == "deepseek-v4-pro"
    assert service.get_settings("u2")["llm"]["model"] == "deepseek-flash"


@pytest.mark.integration
def test_model_settings_api_masks_key():
    app.dependency_overrides[get_current_user] = lambda: {"id": "u1", "username": "tester"}
    service.update_settings("u1", {"llm_api_key": "sk-secret-abcdef"})
    try:
        client = TestClient(app)
        response = client.get("/settings/models")
        assert response.status_code == 200
        payload = response.json()
        assert payload["llm"]["api_key_hint"] == "••••cdef"
        assert "sk-secret-abcdef" not in response.text
        assert [model["id"] for model in payload["catalog"]["llm"][0]["models"]] == [
            "deepseek-flash",
            "deepseek-v4-pro",
        ]

        patched = client.patch(
            "/settings/models",
            json={"llm_model": "deepseek-v4-pro", "llm_api_key": "sk-new-key-1234"},
        )
        assert patched.status_code == 200
        assert patched.json()["llm"]["model"] == "deepseek-v4-pro"
        assert "sk-new-key-1234" not in patched.text

        invalid = client.patch("/settings/models", json={"llm_model": "nope"})
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
def test_embedding_user_key_is_encrypted_and_wins():
    view = service.update_settings(
        "u-embedding", {"embedding_api_key": "sk-embed-12345678"}
    )

    row = model_settings_repo.get("u-embedding")
    assert row is not None
    assert row["embedding_api_key"].startswith("enc:v1:")
    assert "sk-embed-12345678" not in row["embedding_api_key"]
    assert view["embedding"]["key_source"] == "user"
    assert view["embedding"]["mode"] == "remote"
    assert view["embedding"]["api_key_hint"] == "••••5678"
    assert view["embedding"]["dim"] == 1024

    resolved = service.resolve_embedding("u-embedding")
    assert resolved.mode == "remote"
    assert resolved.model == "BAAI/bge-m3"
    assert resolved.api_key == "sk-embed-12345678"
    assert resolved.fingerprint == "remote|siliconflow|BAAI/bge-m3|1024"


@pytest.mark.integration
def test_embedding_key_change_keeps_fingerprint():
    service.update_settings("u-fp", {"embedding_api_key": "sk-first-key"})
    first = service.resolve_embedding("u-fp").fingerprint
    service.update_settings("u-fp", {"embedding_api_key": "sk-second-key"})
    second = service.resolve_embedding("u-fp").fingerprint

    assert first == second


@pytest.mark.integration
def test_clearing_embedding_key_falls_back_to_env_then_local(monkeypatch):
    service.update_settings("u-clear", {"embedding_api_key": "sk-embed-12345678"})
    view = service.update_settings("u-clear", {"embedding_api_key": ""})
    assert view["embedding"]["key_source"] == "env"
    assert service.resolve_embedding("u-clear").api_key == "env-embedding-key"

    monkeypatch.setattr(settings, "embedding_remote_api_key", None)
    local = service.resolve_embedding("u-clear")
    assert local.mode == "local"
    assert local.key_source == "local"
    assert local.model == settings.embedding_model
    assert local.fingerprint.startswith("local|")


@pytest.mark.integration
def test_rerank_user_key_is_used():
    service.update_settings("u-rerank", {"rerank_api_key": "sk-rerank-abcdefgh"})
    resolved = service.resolve_rerank("u-rerank")
    assert resolved.key_source == "user"
    assert resolved.api_key == "sk-rerank-abcdefgh"
    assert resolved.model == "BAAI/bge-reranker-v2-m3"

    service.update_settings("u-rerank", {"rerank_api_key": ""})
    assert service.resolve_rerank("u-rerank").key_source == "env"


@pytest.mark.integration
def test_model_settings_api_exposes_embedding_and_rerank():
    app.dependency_overrides[get_current_user] = lambda: {"id": "u-api", "username": "tester"}
    try:
        client = TestClient(app)
        payload = client.get("/settings/models").json()
        assert payload["embedding"]["model"] == "BAAI/bge-m3"
        assert payload["rerank"]["model"] == "BAAI/bge-reranker-v2-m3"
        assert [model["id"] for model in payload["catalog"]["embedding"][0]["models"]] == [
            "BAAI/bge-m3"
        ]
        assert [model["id"] for model in payload["catalog"]["rerank"][0]["models"]] == [
            "BAAI/bge-reranker-v2-m3"
        ]

        patched = client.patch(
            "/settings/models",
            json={
                "embedding_model": "BAAI/bge-m3",
                "embedding_api_key": "sk-embed-api-1234",
                "rerank_model": "BAAI/bge-reranker-v2-m3",
                "rerank_api_key": "sk-rerank-api-5678",
            },
        )
        assert patched.status_code == 200
        assert patched.json()["embedding"]["key_source"] == "user"
        assert patched.json()["rerank"]["key_source"] == "user"
        assert "sk-embed-api-1234" not in patched.text
        assert "sk-rerank-api-5678" not in patched.text

        invalid = client.patch(
            "/settings/models", json={"embedding_model": "not-a-model"}
        )
        assert invalid.status_code == 422
        invalid_rerank = client.patch(
            "/settings/models", json={"rerank_model": "not-a-model"}
        )
        assert invalid_rerank.status_code == 422
    finally:
        app.dependency_overrides.clear()
