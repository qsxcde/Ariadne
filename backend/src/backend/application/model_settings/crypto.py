"""At-rest encryption for user-supplied model API keys."""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_DEV_FALLBACK_SECRET = "ariadne-local-dev-model-settings"


def _fernet() -> Fernet:
    material = settings.model_settings_encryption_key or settings.jwt_secret_key
    if not material:
        if settings.app_env.strip().lower() not in {"development", "dev", "local", "test", "testing"}:
            raise RuntimeError(
                "MODEL_SETTINGS_ENCRYPTION_KEY (or JWT_SECRET_KEY) is required "
                "to store user model API keys"
            )
        logger.warning(
            "MODEL_SETTINGS_ENCRYPTION_KEY/JWT_SECRET_KEY are unset; "
            "using the local development encryption key"
        )
        material = _DEV_FALLBACK_SECRET
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith(_PREFIX):
        return cleaned
    return _PREFIX + _fernet().encrypt(cleaned.encode("utf-8")).decode("ascii")


def decrypt_api_key(value: str | None) -> str | None:
    if not value:
        return None
    if not value.startswith(_PREFIX):
        # Legacy/plaintext rows should keep working until the user re-saves.
        return value
    try:
        return _fernet().decrypt(value[len(_PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        logger.warning("Cannot decrypt stored model API key: %s", exc)
        return None


def api_key_hint(value: str | None) -> str | None:
    """Return the last four characters only; never expose the full key."""
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) <= 4:
        return "••••"
    return f"••••{cleaned[-4:]}"
