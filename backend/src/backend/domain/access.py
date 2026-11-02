"""Authorization rules that can be evaluated without touching the storage layer."""

from collections.abc import Mapping
from typing import Any


def session_is_accessible(session: Mapping[str, Any] | None, user_id: str | None) -> bool:
    """Return True when ``user_id`` may read/write the given session row.

    Rules:

    * missing or archived sessions are never accessible (callers turn this into 404);
    * sessions created while authentication was disabled have ``user_id = NULL`` and
      stay accessible to everyone (legacy single-user data);
    * otherwise the owner must match exactly.
    """
    if session is None or session.get("is_archived"):
        return False
    owner = session.get("user_id")
    if not owner:
        return True
    return owner == (user_id or None)


def paper_is_accessible(paper: Mapping[str, Any] | None, user_id: str | None) -> bool:
    """Return True when the user may read/write the given paper row.

    Legacy papers created while authentication was disabled have a null owner
    and stay accessible to everyone, matching the session rule.
    """
    if paper is None:
        return False
    owner = paper.get("user_id")
    if not owner:
        return True
    return owner == (user_id or None)
