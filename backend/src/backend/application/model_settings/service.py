"""Resolve and persist per-user model provider settings."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from backend.application.model_settings.catalog import (
    DEFAULT_EMBEDDING_PROVIDER,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_RERANK_PROVIDER,
    EMBEDDING_DIMS,
    LLM_PROVIDERS,
    catalog,
    embedding_providers,
    model_dim,
    model_ids,
    provider_entry,
    rerank_providers,
)
from backend.application.model_settings.crypto import (
    api_key_hint,
    decrypt_api_key,
    encrypt_api_key,
)
from backend.config import settings
from backend.storage.records import SnapshotRecord, UserModelSettingsRecord
from backend.storage.sqlite import model_settings as model_settings_repo


@dataclass(frozen=True)
class ResolvedLLM:
    provider: str
    model: str
    base_url: str
    api_key: str
    key_source: str


@dataclass(frozen=True)
class ResolvedEmbedding:
    mode: str
    provider: str
    model: str
    base_url: str
    api_key: str
    dim: int | None
    key_source: str

    @property
    def fingerprint(self) -> str:
        """Index compatibility signature; deliberately excludes keys and hosts."""
        if self.mode == "local":
            return f"local|{self.model}|{self.dim or 'auto'}"
        return f"remote|{self.provider}|{self.model}|{self.dim or 'auto'}"


@dataclass(frozen=True)
class ResolvedRerank:
    enabled: bool
    provider: str
    model: str
    base_url: str
    api_key: str
    key_source: str

    @property
    def mode(self) -> str:
        return "remote" if self.api_key else "local"


def get_settings(user_id: str | None) -> dict:
    row = model_settings_repo.get(user_id)
    return {
        "llm": _llm_view(row),
        "embedding": _embedding_view(row),
        "rerank": _rerank_view(row),
        "catalog": catalog(),
    }


def update_settings(user_id: str | None, fields: dict) -> dict:
    allowed = {
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
        "embedding_provider",
        "embedding_model",
        "embedding_api_key",
        "embedding_base_url",
        "rerank_provider",
        "rerank_model",
        "rerank_api_key",
        "rerank_base_url",
    }
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unsupported model settings: {', '.join(sorted(unknown))}")

    current = model_settings_repo.get_or_create(user_id)
    updates: dict[str, object] = {}

    _collect_llm_updates(fields, current, updates)
    _collect_embedding_updates(fields, current, updates)
    _collect_rerank_updates(fields, current, updates)

    model_settings_repo.update(user_id, updates)
    return get_settings(user_id)


def resolve_llm(user_id: str | None) -> ResolvedLLM:
    """User key wins; model/provider fall back to the catalog defaults."""
    row = model_settings_repo.get(user_id)
    user_key = decrypt_api_key(row["llm_api_key"]) if row else None
    provider_id = (row["llm_provider"] if row else None) or DEFAULT_LLM_PROVIDER
    provider = provider_entry(LLM_PROVIDERS, provider_id) or LLM_PROVIDERS[0]
    model = (row["llm_model"] if row else None) or DEFAULT_LLM_MODEL
    base_url = (
        (row["llm_base_url"] if row else None)
        or settings.deepseek_base_url
        or provider["base_url"]
    )
    api_key = user_key or (settings.deepseek_api_key or "")
    if not api_key:
        raise ValueError("No LLM API key configured")
    return ResolvedLLM(
        provider=provider_id,
        model=model,
        base_url=base_url,
        api_key=api_key,
        key_source="user" if user_key else "env",
    )


def resolve_embedding(user_id: str | None) -> ResolvedEmbedding:
    """Resolve the embedding runtime; user key > env key > local model."""
    row = model_settings_repo.get(user_id)
    user_key = decrypt_api_key(row["embedding_api_key"]) if row else None
    provider_id = (
        row["embedding_provider"] if row else None
    ) or DEFAULT_EMBEDDING_PROVIDER
    providers = embedding_providers()
    provider = provider_entry(providers, provider_id) or providers[0]
    model = (row["embedding_model"] if row else None) or settings.embedding_remote_model
    base_url = (
        (row["embedding_base_url"] if row else None)
        or settings.embedding_remote_base_url
        or provider["base_url"]
    )
    api_key = user_key or (settings.embedding_remote_api_key or "")

    if not api_key:
        return ResolvedEmbedding(
            mode="local",
            provider="local",
            model=settings.embedding_model,
            base_url="",
            api_key="",
            dim=settings.embedding_dim,
            key_source="local",
        )

    dim = model_dim(provider, model) or EMBEDDING_DIMS.get(model)
    if dim is None and row is not None:
        dim = row["embedding_dim"]
    return ResolvedEmbedding(
        mode="remote",
        provider=provider_id,
        model=model,
        base_url=base_url,
        api_key=api_key,
        dim=dim,
        key_source="user" if user_key else "env",
    )


def resolve_rerank(user_id: str | None) -> ResolvedRerank:
    """Resolve the rerank runtime; user key > env key > local fallback."""
    row = model_settings_repo.get(user_id)
    user_key = decrypt_api_key(row["rerank_api_key"]) if row else None
    provider_id = (row["rerank_provider"] if row else None) or DEFAULT_RERANK_PROVIDER
    providers = rerank_providers()
    provider = provider_entry(providers, provider_id) or providers[0]
    model = (row["rerank_model"] if row else None) or settings.reranker_remote_model
    base_url = (
        (row["rerank_base_url"] if row else None)
        or settings.reranker_remote_base_url
        or provider["base_url"]
    )
    api_key = user_key or (settings.embedding_remote_api_key or "")
    return ResolvedRerank(
        enabled=settings.reranker_enabled,
        provider=provider_id,
        model=model,
        base_url=base_url,
        api_key=api_key,
        key_source="user" if user_key else ("env" if api_key else "local"),
    )


def env_embedding_fingerprint() -> str:
    """Fingerprint of an index built before per-user settings existed (v17)."""
    if settings.embedding_remote_api_key:
        model = settings.embedding_remote_model
        dim = EMBEDDING_DIMS.get(model)
        return f"remote|siliconflow|{model}|{dim or 'auto'}"
    return f"local|{settings.embedding_model}|{settings.embedding_dim}"


def index_embedding_status(
    active_index: SnapshotRecord | None, user_id: str | None
) -> dict:
    """Compare the active index fingerprint with the user's current embedder."""
    current = resolve_embedding(user_id)
    if active_index is None:
        return {
            "stale": False,
            "current_model": current.model,
            "current_mode": current.mode,
            "index_model": None,
        }

    stored = active_index.get("embedding_fingerprint")
    baseline = stored or env_embedding_fingerprint()
    return {
        "stale": baseline != current.fingerprint,
        "current_model": current.model,
        "current_mode": current.mode,
        "index_model": active_index.get("embedding_model"),
    }


def _collect_llm_updates(
    fields: dict, current: UserModelSettingsRecord, updates: dict[str, object]
) -> None:
    provider_id = str(
        fields.get("llm_provider") or current["llm_provider"] or DEFAULT_LLM_PROVIDER
    )
    provider = provider_entry(LLM_PROVIDERS, provider_id)
    if provider is None:
        raise ValueError(f"Unsupported LLM provider: {provider_id}")

    model = str(fields.get("llm_model") or current["llm_model"] or DEFAULT_LLM_MODEL)
    if model not in model_ids(provider):
        raise ValueError(f"Unsupported LLM model for {provider_id}: {model}")

    if "llm_provider" in fields or provider_id != current["llm_provider"]:
        updates["llm_provider"] = provider_id
    if "llm_model" in fields or model != current["llm_model"]:
        updates["llm_model"] = model
    if "llm_base_url" in fields:
        updates["llm_base_url"] = _validated_base_url(fields["llm_base_url"], "LLM")
    _collect_key_update(fields, updates, "llm_api_key")


def _collect_embedding_updates(
    fields: dict, current: UserModelSettingsRecord, updates: dict[str, object]
) -> None:
    providers = embedding_providers()
    provider_id = str(
        fields.get("embedding_provider")
        or current["embedding_provider"]
        or DEFAULT_EMBEDDING_PROVIDER
    )
    if "embedding_provider" in fields and provider_entry(providers, provider_id) is None:
        raise ValueError(f"Unsupported embedding provider: {provider_id}")
    provider = provider_entry(providers, provider_id) or providers[0]

    model = str(
        fields.get("embedding_model")
        or current["embedding_model"]
        or settings.embedding_remote_model
    )
    if "embedding_model" in fields and model not in model_ids(provider):
        raise ValueError(f"Unsupported embedding model for {provider_id}: {model}")

    if "embedding_provider" in fields or provider_id != current["embedding_provider"]:
        updates["embedding_provider"] = provider_id
    if "embedding_model" in fields or model != current["embedding_model"]:
        updates["embedding_model"] = model
        dim = model_dim(provider, model)
        if dim is not None:
            updates["embedding_dim"] = dim
    if "embedding_base_url" in fields:
        updates["embedding_base_url"] = _validated_base_url(
            fields["embedding_base_url"], "Embedding"
        )
    _collect_key_update(fields, updates, "embedding_api_key")


def _collect_rerank_updates(
    fields: dict, current: UserModelSettingsRecord, updates: dict[str, object]
) -> None:
    providers = rerank_providers()
    provider_id = str(
        fields.get("rerank_provider")
        or current["rerank_provider"]
        or DEFAULT_RERANK_PROVIDER
    )
    if "rerank_provider" in fields and provider_entry(providers, provider_id) is None:
        raise ValueError(f"Unsupported rerank provider: {provider_id}")
    provider = provider_entry(providers, provider_id) or providers[0]

    model = str(
        fields.get("rerank_model")
        or current["rerank_model"]
        or settings.reranker_remote_model
    )
    if "rerank_model" in fields and model not in model_ids(provider):
        raise ValueError(f"Unsupported rerank model for {provider_id}: {model}")

    if "rerank_provider" in fields or provider_id != current["rerank_provider"]:
        updates["rerank_provider"] = provider_id
    if "rerank_model" in fields or model != current["rerank_model"]:
        updates["rerank_model"] = model
    if "rerank_base_url" in fields:
        updates["rerank_base_url"] = _validated_base_url(
            fields["rerank_base_url"], "Rerank"
        )
    _collect_key_update(fields, updates, "rerank_api_key")


def _collect_key_update(
    fields: dict, updates: dict[str, object], field: str
) -> None:
    if field not in fields:
        return
    raw_key = fields[field]
    if raw_key is None or not str(raw_key).strip():
        updates[field] = None
    else:
        updates[field] = encrypt_api_key(str(raw_key))


def _validated_base_url(value: object, label: str) -> str | None:
    base_url = str(value or "").strip()
    if base_url and urlparse(base_url).scheme not in {"http", "https"}:
        raise ValueError(f"{label} base URL must be http(s)")
    return base_url or None


def _llm_view(row: UserModelSettingsRecord | None) -> dict:
    user_key = decrypt_api_key(row["llm_api_key"]) if row else None
    provider_id = (row["llm_provider"] if row else None) or DEFAULT_LLM_PROVIDER
    provider = provider_entry(LLM_PROVIDERS, provider_id) or LLM_PROVIDERS[0]
    model = (row["llm_model"] if row else None) or DEFAULT_LLM_MODEL
    effective_key = user_key or settings.deepseek_api_key
    return {
        "provider": provider_id,
        "model": model,
        "base_url": (row["llm_base_url"] if row else None) or provider["base_url"],
        "api_key_set": bool(effective_key),
        "api_key_hint": api_key_hint(user_key) if user_key else None,
        "key_source": "user" if user_key else "env",
    }


def _embedding_view(row: UserModelSettingsRecord | None) -> dict:
    user_key = decrypt_api_key(row["embedding_api_key"]) if row else None
    provider_id = (
        row["embedding_provider"] if row else None
    ) or DEFAULT_EMBEDDING_PROVIDER
    providers = embedding_providers()
    provider = provider_entry(providers, provider_id) or providers[0]
    model = (row["embedding_model"] if row else None) or settings.embedding_remote_model
    effective_key = user_key or settings.embedding_remote_api_key
    dim = model_dim(provider, model) or EMBEDDING_DIMS.get(model)
    if dim is None and row is not None:
        dim = row["embedding_dim"]
    return {
        "provider": provider_id,
        "model": model,
        "base_url": (
            (row["embedding_base_url"] if row else None)
            or settings.embedding_remote_base_url
            or provider["base_url"]
        ),
        "api_key_set": bool(effective_key),
        "api_key_hint": api_key_hint(user_key) if user_key else None,
        "key_source": "user" if user_key else ("env" if effective_key else "local"),
        "mode": "remote" if effective_key else "local",
        "dim": dim,
    }


def _rerank_view(row: UserModelSettingsRecord | None) -> dict:
    user_key = decrypt_api_key(row["rerank_api_key"]) if row else None
    provider_id = (row["rerank_provider"] if row else None) or DEFAULT_RERANK_PROVIDER
    providers = rerank_providers()
    provider = provider_entry(providers, provider_id) or providers[0]
    model = (row["rerank_model"] if row else None) or settings.reranker_remote_model
    effective_key = user_key or settings.embedding_remote_api_key
    return {
        "enabled": settings.reranker_enabled,
        "provider": provider_id,
        "model": model,
        "base_url": (
            (row["rerank_base_url"] if row else None)
            or settings.reranker_remote_base_url
            or provider["base_url"]
        ),
        "api_key_set": bool(effective_key),
        "api_key_hint": api_key_hint(user_key) if user_key else None,
        "key_source": "user" if user_key else ("env" if effective_key else "local"),
        "mode": "remote" if effective_key else "local",
    }
