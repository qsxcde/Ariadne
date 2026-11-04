"""Per-user model provider settings and catalogs."""

from typing import Literal

from pydantic import BaseModel, Field


class ModelOption(BaseModel):
    id: str
    label: str
    dim: int | None = None


class ProviderCatalog(BaseModel):
    id: str
    label: str
    base_url: str | None = None
    models: list[ModelOption] = Field(default_factory=list)


class ModelCatalog(BaseModel):
    llm: list[ProviderCatalog] = Field(default_factory=list)
    embedding: list[ProviderCatalog] = Field(default_factory=list)
    rerank: list[ProviderCatalog] = Field(default_factory=list)


class LlmSettingsView(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    api_key_set: bool
    api_key_hint: str | None = None
    key_source: Literal["user", "env"]


class EmbeddingSettingsView(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    api_key_set: bool
    api_key_hint: str | None = None
    key_source: Literal["user", "env", "local"]
    mode: Literal["remote", "local"]
    dim: int | None = None


class RerankSettingsView(BaseModel):
    enabled: bool
    provider: str
    model: str
    base_url: str | None = None
    api_key_set: bool
    api_key_hint: str | None = None
    key_source: Literal["user", "env", "local"]
    mode: Literal["remote", "local"]


class ModelSettingsResponse(BaseModel):
    llm: LlmSettingsView
    embedding: EmbeddingSettingsView
    rerank: RerankSettingsView
    catalog: ModelCatalog


class ModelSettingsUpdate(BaseModel):
    """PATCH fields; omitted = unchanged, empty api key = clear the user key."""

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    rerank_provider: str | None = None
    rerank_model: str | None = None
    rerank_api_key: str | None = None
    rerank_base_url: str | None = None
