"""Model catalogs exposed to the settings UI.

LLM entries are static because the DeepSeek API surface is stable. Embedding
and rerank catalogs follow the models configured in the environment so the UI
never offers a model the backend cannot serve.
"""

from __future__ import annotations

from backend.config import settings

DEFAULT_LLM_PROVIDER = "deepseek"
DEFAULT_LLM_MODEL = "deepseek-flash"
DEFAULT_EMBEDDING_PROVIDER = "siliconflow"
DEFAULT_RERANK_PROVIDER = "siliconflow"

# Dimensions are only used for fingerprinting and empty-index sizing; the
# vector dimension is ultimately taken from the first batch of vectors.
EMBEDDING_DIMS: dict[str, int] = {
    "BAAI/bge-m3": 1024,
    "BAAI/bge-small-en-v1.5": 384,
    "Qwen/Qwen3-Embedding-0.6B": 1024,
}

LLM_PROVIDERS: list[dict] = [
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": [
            {"id": "deepseek-flash", "label": "DeepSeek Flash"},
            {"id": "deepseek-v4-pro", "label": "DeepSeek V4 Pro"},
        ],
    }
]


def embedding_providers() -> list[dict]:
    model = settings.embedding_remote_model
    return [
        {
            "id": "siliconflow",
            "label": "硅基流动 SiliconFlow",
            "base_url": settings.embedding_remote_base_url,
            "models": [
                {
                    "id": model,
                    "label": model,
                    "dim": EMBEDDING_DIMS.get(model),
                }
            ],
        }
    ]


def rerank_providers() -> list[dict]:
    model = settings.reranker_remote_model
    return [
        {
            "id": "siliconflow",
            "label": "硅基流动 SiliconFlow",
            "base_url": settings.reranker_remote_base_url,
            "models": [{"id": model, "label": model}],
        }
    ]


def catalog() -> dict[str, list[dict]]:
    return {
        "llm": LLM_PROVIDERS,
        "embedding": embedding_providers(),
        "rerank": rerank_providers(),
    }


def provider_entry(providers: list[dict], provider_id: str) -> dict | None:
    return next((item for item in providers if item["id"] == provider_id), None)


def model_ids(provider: dict) -> set[str]:
    return {model["id"] for model in provider.get("models", [])}


def model_dim(provider: dict, model_id: str) -> int | None:
    for model in provider.get("models", []):
        if model["id"] == model_id:
            return model.get("dim")
    return None
