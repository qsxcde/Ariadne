"""Alert preferences use case."""

from typing import Any

from backend.storage.sqlite import alerts as alert_repo


def get_settings(user_id: str | None) -> dict[str, Any]:
    return dict(alert_repo.get_or_create(user_id))


def update_settings(user_id: str | None, **fields: Any) -> dict[str, Any]:
    return dict(alert_repo.update(user_id, **fields))
