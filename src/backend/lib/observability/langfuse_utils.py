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
        tags: list[str] | None = None,
) -> None:
    client = get_langfuse_client(tags[0])
    if client is None:
        return

    kwargs: dict[str, Any] = {}
    if name is not None:
        kwargs["name"] = name
    if input_data is not None:
        kwargs["input"] = anonymize_state_fragment(input_data)
    if output_data is not None:
        kwargs["output"] = anonymize_state_fragment(output_data)
    if metadata is not None:
        kwargs["metadata"] = sanitize_value(metadata)
    if level is not None:
        kwargs["level"] = level
    if status_message is not None:
        kwargs["status_message"] = status_message

    client.update_current_span(**kwargs)


def log_langfuse_generation(
        *,
        name: str,
        model_input: Any,
        response: dict[str, Any],
        latency_ms: float,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
) -> None:
    client = get_langfuse_client(tags[0])
    if client is None:
        return

    usage = response.get("usage", {})
    cost_details = usage.get("cost_details", {})

    kwargs = {
        "name": name,
        "model": response.get("model"),
        "input": anonymize_state_fragment(model_input),
        "output": anonymize_state_fragment(response.get("choices")),
        "usage_details": {
            "input": usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        },
        "cost_details": {
            "input": cost_details.get("upstream_inference_prompt_cost", 0.0),
            "output": cost_details.get("upstream_inference_completions_cost", 0.0),
            "total": cost_details.get("upstream_inference_cost", 0.0),
        },
        "metadata": sanitize_value({
            **(metadata or {}),
            "latency_ms": latency_ms,
        }),
    }

    client.update_current_generation(**kwargs)


def log_eval_scores(scores: dict[str, float], comment: str | None = None, tags=None) -> None:
    client = get_langfuse_client(tags[0])
    if client is None:
        return

    for name, value in scores.items():
        client.score_current_trace(
            name=name,
            value=float(value),
            comment=comment,
        )


def flush_langfuse(tags=None) -> None:
    client = get_langfuse_client(tags[0])
    if client is not None:
        client.flush()


__all__ = [
    "observe",
    "anonymize_user_id",
    "sanitize_value",
    "update_current_observation",
    "log_langfuse_generation",
    "log_eval_scores",
    "flush_langfuse",
]
