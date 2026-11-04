"""Notification outbox and webhook delivery."""

import json

import pytest

from backend.application.follow.feed import FakeFeedSource, create_subscription, refresh_feed
from backend.application.follow.notifications import (
    SmtpChannel,
    create_notification,
    deliver_pending,
    list_notifications,
    mark_read,
)
from backend.config import settings


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, notification: dict) -> None:
        self.sent.append(dict(notification))


@pytest.mark.integration
def test_notifications_create_read_and_deliver():
    created = create_notification(
        "u1", kind="feed", title="New paper", body="1 new item"
    )
    assert created["status"] == "unread"
    assert list_notifications("u1", status="unread")[0]["id"] == created["id"]

    read = mark_read(created["id"], "u1")
    assert read is not None and read["status"] == "read"

    pending = create_notification(
        "u1", kind="feed", title="Another", body="2 new items"
    )
    channel = FakeChannel()
    result = deliver_pending("u1", channel=channel)

    assert result == {"pending": 1, "delivered": 1}
    assert channel.sent[0]["id"] == pending["id"]
    assert list_notifications("u1", status="delivered")[0]["id"] == pending["id"]


@pytest.mark.unit
def test_smtp_channel_sends_email(monkeypatch):
    sent: list[object] = []

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            self.host = host

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "ariadne@example.com")
    monkeypatch.setattr("backend.application.follow.notifications.smtplib.SMTP", FakeSmtp)
    notification = create_notification(
        "u1", kind="feed", title="New paper", body="body"
    )

    SmtpChannel("reader@example.com").send(notification)

    assert sent
    assert sent[0]["To"] == "reader@example.com"


@pytest.mark.integration
def test_feed_refresh_creates_notification():
    create_subscription("u1", kind="keyword", value="RAG")
    source = FakeFeedSource(
        [
            {
                "external_id": "arxiv-1",
                "title": "Paper",
                "authors_json": json.dumps(["Alice"]),
                "abstract": "Abstract",
                "url": "https://arxiv.org/abs/1",
                "published_at": "2026-11-01",
            }
        ]
    )

    refresh_feed("u1", source=source)

    notifications = list_notifications("u1", status="unread")
    assert notifications
    assert notifications[0]["kind"] == "feed"
