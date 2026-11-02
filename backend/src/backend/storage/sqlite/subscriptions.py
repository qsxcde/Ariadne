"""Feed subscriptions."""

import uuid
from typing import cast

from backend.core.model.records import SubscriptionRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso


def create_subscription(
    *,
    user_id: str | None,
    kind: str,
    value: str,
    subscription_id: str | None = None,
) -> SubscriptionRecord:
    normalized = value.strip()
    if kind not in {"keyword", "author", "venue", "institution"}:
        raise ValueError(f"Invalid subscription kind: {kind}")
    if not normalized:
        raise ValueError("Subscription value is empty")
    resolved_id = subscription_id or str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO subscriptions (
              id, user_id, kind, value, is_active, created_at, last_checked_at
            )
            VALUES (?, ?, ?, ?, 1, ?, NULL)
            """,
            (resolved_id, user_id, kind, normalized, now_iso()),
        )
        row = conn.execute(
            """
            SELECT * FROM subscriptions
            WHERE user_id IS ? AND kind = ? AND value = ?
            """,
            (user_id, kind, normalized),
        ).fetchone()
    if row is None:
        raise RuntimeError("创建订阅失败")
    return cast(SubscriptionRecord, dict(row))


def get_subscription(subscription_id: str) -> SubscriptionRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE id = ?", (subscription_id,)
        ).fetchone()
        return cast(SubscriptionRecord | None, row_to_dict(row))


def list_subscriptions(
    user_id: str | None, *, active_only: bool = True
) -> list[SubscriptionRecord]:
    sql = "SELECT * FROM subscriptions WHERE user_id IS ?"
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY created_at ASC"
    with connect() as conn:
        rows = conn.execute(sql, (user_id,)).fetchall()
    return [cast(SubscriptionRecord, dict(row)) for row in rows]


def delete_subscription(subscription_id: str, user_id: str | None) -> bool:
    with transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id IS ?",
            (subscription_id, user_id),
        )
    return cursor.rowcount > 0


def mark_checked(subscription_id: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE subscriptions SET last_checked_at = ? WHERE id = ?",
            (now_iso(), subscription_id),
        )
