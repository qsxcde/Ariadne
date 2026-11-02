"""Notification creation and optional webhook delivery."""

from typing import Any, Protocol

import httpx

from backend.core.model.records import NotificationRecord
from backend.storage.sqlite import notifications as notification_repo


class NotificationChannel(Protocol):
    def send(self, notification: NotificationRecord) -> None: ...


class WebhookChannel:
    def __init__(self, url: str) -> None:
        self.url = url

    def send(self, notification: NotificationRecord) -> None:
        response = httpx.post(
            self.url,
            json={
                "kind": notification["kind"],
                "title": notification["title"],
                "body": notification["body"],
                "created_at": notification["created_at"],
            },
            timeout=10,
        )
        response.raise_for_status()


def create_notification(
    user_id: str | None, *, kind: str, title: str, body: str
) -> NotificationRecord:
    return notification_repo.create_notification(
        user_id=user_id, kind=kind, title=title, body=body
    )


def list_notifications(
    user_id: str | None, *, status: str | None = None
) -> list[NotificationRecord]:
    return notification_repo.list_notifications(user_id, status=status)


def mark_read(
    notification_id: str, user_id: str | None
) -> NotificationRecord | None:
    return notification_repo.mark_read(notification_id, user_id)


def deliver_pending(
    user_id: str | None,
    *,
    channel: NotificationChannel | None = None,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    target = channel or (WebhookChannel(webhook_url) if webhook_url else None)
    if target is None:
        raise ValueError("No notification channel configured")
    pending = notification_repo.list_notifications(
        user_id, status="unread", limit=100
    )
    delivered = 0
    for notification in pending:
        target.send(notification)
        notification_repo.mark_delivered(notification["id"])
        delivered += 1
    return {"pending": len(pending), "delivered": delivered}
