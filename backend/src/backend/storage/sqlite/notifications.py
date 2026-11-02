"""In-app notification outbox."""

import uuid
from typing import cast

from backend.core.model.records import NotificationRecord
from backend.storage.sqlite.connection import connect, row_to_dict, transaction
from backend.storage.sqlite.sessions import now_iso


def create_notification(
    *,
    user_id: str | None,
    kind: str,
    title: str,
    body: str,
) -> NotificationRecord:
    notification_id = str(uuid.uuid4())
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO notifications (
              id, user_id, kind, title, body, status, created_at, delivered_at
            )
            VALUES (?, ?, ?, ?, ?, 'unread', ?, NULL)
            """,
            (notification_id, user_id, kind, title, body, now_iso()),
        )
    row = get_notification(notification_id)
    if row is None:
        raise RuntimeError("创建通知失败")
    return row


def get_notification(notification_id: str) -> NotificationRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM notifications WHERE id = ?", (notification_id,)
        ).fetchone()
        return cast(NotificationRecord | None, row_to_dict(row))


def list_notifications(
    user_id: str | None, *, status: str | None = None, limit: int = 50
) -> list[NotificationRecord]:
    sql = "SELECT * FROM notifications WHERE user_id IS ?"
    params: list[object] = [user_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(max(1, min(limit, 200)))
    with connect() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [cast(NotificationRecord, dict(row)) for row in rows]


def mark_read(notification_id: str, user_id: str | None) -> NotificationRecord | None:
    with transaction() as conn:
        conn.execute(
            "UPDATE notifications SET status = 'read' WHERE id = ? AND user_id IS ?",
            (notification_id, user_id),
        )
    return get_notification(notification_id)


def mark_delivered(notification_id: str) -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE notifications SET status = 'delivered', delivered_at = ? WHERE id = ?",
            (now_iso(), notification_id),
        )
