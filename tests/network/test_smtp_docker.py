"""Real SMTP delivery test against Docker MailHog."""

import os
import time

import httpx
import pytest

from backend.application.follow.notifications import create_notification, deliver_pending
from backend.config import settings

pytestmark = [
    pytest.mark.smtp_docker,
    pytest.mark.skipif(
        os.getenv("SCIPAL_SMTP_DOCKER") != "1",
        reason="run scripts/run_smtp_test.sh",
    ),
]


def test_smtp_delivery_reaches_mailhog(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", 1025)
    monkeypatch.setattr(settings, "smtp_from", "scipal@example.com")
    monkeypatch.setattr(settings, "smtp_username", None)
    monkeypatch.setattr(settings, "smtp_starttls", False)

    notification = create_notification(
        "u1",
        kind="feed",
        title="SciPal test notification",
        body="hello from smtp test",
    )
    result = deliver_pending(
        "u1",
        email_to="reader@example.com",
    )
    assert result["delivered"] == 1

    messages = []
    for _ in range(20):
        response = httpx.get("http://127.0.0.1:8025/api/v2/messages", timeout=5)
        response.raise_for_status()
        messages = response.json().get("items", [])
        if messages:
            break
        time.sleep(0.25)

    assert messages
    headers = messages[0]["Content"]["Headers"]
    assert headers["Subject"][0] == "SciPal test notification"
    assert "reader@example.com" in str(headers.get("To", []))
    assert notification["id"]
