"""Per-user completer construction is cached by the resolved config."""

import pytest

from backend import composition
from backend.application.model_settings.service import ResolvedLLM


@pytest.mark.unit
def test_user_completer_is_cached_by_effective_config(monkeypatch):
    resolved = ResolvedLLM(
        provider="deepseek",
        model="deepseek-flash",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        key_source="user",
    )
    monkeypatch.setattr(
        "backend.application.model_settings.service.resolve_llm",
        lambda user_id: resolved,
    )
    composition._user_completers.clear()

    first = composition.user_text_completer("u1")
    second = composition.user_text_completer("u1")
    assert first is second
    assert first.model == "deepseek-flash"

    changed = ResolvedLLM(
        provider="deepseek",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
        api_key="sk-test",
        key_source="user",
    )
    monkeypatch.setattr(
        "backend.application.model_settings.service.resolve_llm",
        lambda user_id: changed,
    )
    third = composition.user_text_completer("u1")
    assert third is not first
    assert third.model == "deepseek-v4-pro"
