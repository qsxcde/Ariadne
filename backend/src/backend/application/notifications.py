"""Notification creation and optional webhook delivery."""

import smtplib
from email.message import EmailMessage
from typing import Any, Protocol

import httpx

from backend.config import settings
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


class SmtpChannel:
    def __init__(self, recipient: str) -> None:
        self.recipient = recipient

    def send(self, notification: NotificationRecord) -> None:
        if not settings.smtp_host or not settings.smtp_from:
            raise ValueError("SMTP is not configured")
        message = EmailMessage()
        message["Subject"] = notification["title"]
        message["From"] = settings.smtp_from
        message["To"] = self.recipient
        message.set_content(notification["body"])
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=10
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)


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
    email_to: str | None = None,
) -> dict[str, Any]:
    target = channel
    if target is None and webhook_url:
        target = WebhookChannel(webhook_url)
    if target is None and email_to:
        target = SmtpChannel(email_to)
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
