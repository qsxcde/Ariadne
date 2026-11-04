"""Normalise structured payloads returned by LLM providers.

LLMs routinely wrap JSON in Markdown fences. This module is the single place
that knows how to unwrap and validate such payloads.
"""

import json
from typing import Any


def strip_markdown_fence(text: str) -> str:
    """Remove a surrounding ```json ... ``` (or ``` ... ```) fence."""
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    newline = cleaned.find("\n")
    if newline == -1:
        # Single-line payload: ```json {"a": 1}```
        body = cleaned[3:]
        if body[:4].lower() == "json":
            body = body[4:]
        return body.strip().strip("`").strip()

    body = cleaned[newline + 1 :]
    stripped_tail = body.rstrip()
    if stripped_tail.endswith("```"):
        body = stripped_tail[:-3]
    return body.strip()


def extract_json_object_text(text: str) -> str:
    """Reduce raw LLM output to the outermost ``{...}`` span.

    Falls back to the fence-stripped text when no braces are present, so the
    caller's single ``json.loads`` keeps producing one obvious error.
    """
    cleaned = strip_markdown_fence(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def parse_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object out of raw LLM output.

    Handles Markdown fences and surrounding prose, so every caller can keep a
    single ``except`` branch for "the model misbehaved".
    """
    payload = json.loads(extract_json_object_text(text))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object, got {type(payload).__name__}")
    return payload
