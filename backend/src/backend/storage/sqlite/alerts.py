"""Local alert and digest preferences."""

import uuid
from typing import cast

from backend.core.model.records import AlertSettingsRecord
from backend.storage.sqlite.connection import connect, transaction
from backend.storage.sqlite.sessions import now_iso


def get_or_create(user_id: str | None) -> AlertSettingsRecord:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM alert_settings WHERE user_id IS ?", (user_id,)
        ).fetchone()
    if row is not None:
        return cast(AlertSettingsRecord, dict(row))

    settings_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO alert_settings (
              id, user_id, new_paper, new_version, new_citation,
              digest_enabled, digest_frequency, updated_at
            )
            VALUES (?, ?, 1, 1, 0, 1, 'weekly', ?)
            """,
            (settings_id, user_id, now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM alert_settings WHERE user_id IS ?", (user_id,)
        ).fetchone()
    if row is None:
        raise RuntimeError("创建提醒设置失败")
    return cast(AlertSettingsRecord, dict(row))


def update(
    user_id: str | None,
    *,
    new_paper: int | None = None,
    new_version: int | None = None,
    new_citation: int | None = None,
    digest_enabled: int | None = None,
    digest_frequency: str | None = None,
) -> AlertSettingsRecord:
    get_or_create(user_id)
    assignments: list[str] = []
    values: list[object] = []
    for column, value in (
        ("new_paper", new_paper),
        ("new_version", new_version),
        ("new_citation", new_citation),
        ("digest_enabled", digest_enabled),
        ("digest_frequency", digest_frequency),
    ):
        if value is not None:
            assignments.append(f"{column} = ?")
            values.append(value)
    if assignments:
        assignments.append("updated_at = ?")
        values.extend([now_iso(), user_id])
        with transaction() as conn:
            conn.execute(
                f"UPDATE alert_settings SET {', '.join(assignments)} WHERE user_id IS ?",
                tuple(values),
            )
    return get_or_create(user_id)
