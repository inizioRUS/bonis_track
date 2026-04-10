from __future__ import annotations

import hashlib
from typing import Any

from langfuse import observe

from lib.observability.langfuse_client import get_langfuse_client
from lib.security.anonymization import anonymize_state_fragment

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "email",
    "phone",
    "notes",
    "text",
    "content",
    "final_answer",
}


def anonymize_user_id(user_id: str) -> str:
    if not user_id:
        return "anonymous"
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if key.lower() in SENSITIVE_KEYS else sanitize_value(val))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [sanitize_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(v) for v in value)
    if isinstance(value, str) and len(value) > 1000:
        return value[:1000] + "...[truncated]"
    return value


def update_current_observation(
        *,
        name: str | None = None,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
        level: str | None = None,
        status_message: str | None = None,
) -> None:
    client = get_langfuse_client()
    if client is None:
        return

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if input_data is not None:
        kwargs["input"] = anonymize_state_fragment(input_data)
    if output_data is not None:
        kwargs["output"] = output_data
    if metadata is not None:
        kwargs["metadata"] = metadata
    if level is not None:
        kwargs["level"] = level
    if status_message is not None:
        kwargs["status_message"] = status_message

    client.update_current_span(**kwargs)


def log_langfuse_generation(
        *,
        name: str,
        model_input: Any,
        response,
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
) -> None:
    client = get_langfuse_client()
    client.update_current_generation(
        name=name,
        model=response['model'],
        input=anonymize_state_fragment(model_input),
        output=response['choices'],
        usage_details={
            "input": response["usage"]["prompt_tokens"],
            "output": response["usage"]["completion_tokens"],
            "total": response["usage"]["total_tokens"],
        },
        cost_details={
            "input": response["usage"]["cost_details"]["upstream_inference_cost"],
            "output": response["usage"]["cost_details"]["upstream_inference_prompt_cost"],
            'total':response["usage"]["cost_details"]["upstream_inference_completions_cost"]
        },
        metadata={
            **(metadata or {}),
            "latency_ms": latency_ms
        },
    )


def log_trace_score(
        *,
        name: str,
        value: float,
        comment: str | None = None,
) -> None:
    client = get_langfuse_client()
    client.score_current_trace(
        name=name,
        value=value,
        comment=comment,
    )


def flush_langfuse() -> None:
    client = get_langfuse_client()
    if client is not None:
        client.flush()


__all__ = ["observe", "anonymize_user_id", "sanitize_value", "update_current_observation", "flush_langfuse"]
