"""Per-user model provider settings."""

import uuid
from typing import cast

from backend.storage.records import UserModelSettingsRecord
from backend.storage.sqlite.connection import connect, transaction
from backend.storage.sqlite.sessions import now_iso


def get(user_id: str | None) -> UserModelSettingsRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM user_model_settings WHERE user_id IS ?", (user_id,)
        ).fetchone()
    return cast(UserModelSettingsRecord, dict(row)) if row is not None else None


def get_or_create(user_id: str | None) -> UserModelSettingsRecord:
    row = get(user_id)
    if row is not None:
        return row

    with transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_model_settings (id, user_id, updated_at)
            VALUES (?, ?, ?)
            """,
            (str(uuid.uuid4()), user_id, now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM user_model_settings WHERE user_id IS ?", (user_id,)
        ).fetchone()
    if row is None:
        raise RuntimeError("创建模型设置失败")
    return cast(UserModelSettingsRecord, dict(row))


def update(user_id: str | None, fields: dict[str, object]) -> UserModelSettingsRecord:
    get_or_create(user_id)
    if fields:
        assignments = [f"{column} = ?" for column in fields]
        assignments.append("updated_at = ?")
        values = [*fields.values(), now_iso(), user_id]
        with transaction() as conn:
            conn.execute(
                f"UPDATE user_model_settings SET {', '.join(assignments)} WHERE user_id IS ?",
                tuple(values),
            )
    return get_or_create(user_id)
