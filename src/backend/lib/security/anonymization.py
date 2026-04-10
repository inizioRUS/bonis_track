from __future__ import annotations

import hashlib
import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\-\s()]{7,}\d)(?!\w)")
ASANA_GID_RE = re.compile(r"\b\d{8,20}\b")
URL_TOKEN_RE = re.compile(r'([?&](?:token|key|auth|sig|signature|access_token)=)[^&]+', re.IGNORECASE)

SENSITIVE_KEYS = {
    "user_id",
    "username",
    "email",
    "phone",
    "url",
    "notes",
    "text",
    "name",
    "query",
    "content",
    "final_answer",
}

MASK = "***"


def stable_hash(value: str, prefix: str = "hash") -> str:
    if not value:
        return value
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def anonymize_text(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    text = EMAIL_RE.sub("[EMAIL]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    text = URL_TOKEN_RE.sub(r"\1[REDACTED]", text)

    # если хочешь скрывать numeric ids
    text = ASANA_GID_RE.sub("[ID]", text)

    return text


def anonymize_value(value: Any, key: str | None = None) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        if key in {"user_id", "username", "session_id"}:
            return stable_hash(value, key)
        if key == "url":
            return anonymize_text(value)
        return anonymize_text(value)

    if isinstance(value, list):
        return [anonymize_value(v) for v in value]

    if isinstance(value, tuple):
        return tuple(anonymize_value(v) for v in value)

    if isinstance(value, dict):
        return anonymize_dict(value)

    return value


def anonymize_dict(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in SENSITIVE_KEYS:
            result[key] = anonymize_value(value, key=key)
        else:
            result[key] = anonymize_value(value, key=key)
    return result


def anonymize_state_fragment(data: Any) -> Any:
    return anonymize_value(data)