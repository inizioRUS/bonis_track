from __future__ import annotations
import time
from lib.multi_agent.state import WorkflowState
from lib.multi_agent.tools.memory import MemoryTool
from lib.llm.llm_client_open_router import LLMClient
from lib.observability.langfuse_utils import (
    observe,
    log_langfuse_generation,
)


def _build_memory_merge_prompt(
        *,
        user_query: str,
        existing_items: list[dict],
        final_answer: str,
) -> str:
    return f"""
You are a memory consolidation module.

Your task is to merge existing memory items with result of answer and new information.

You don't need make summarize of answer, only actual key fact.

Rules:
- Return a final list of memory items.
- Preserve useful old memory items unless they are clearly superseded.
- Update existing items when the new item describes the same entity more precisely.
- Prefer newer candidate items when they conflict with older items.
- Do not create duplicates.
- Keep the exact structure of each item:
  {{
    "content": string,
  }}
- If two items refer to the same entity, keep one merged item.
- The "content" field should stay in normalized format like:
  "project: Backend API -> 123456789"
- focus on save id and url of all object(documents, task, projects etc)
User query:
{user_query}

Existing memory items:
{existing_items}

Final answer:
{final_answer}

Return JSON with exactly this structure:
{{
  "items": [ ... ]
}}
"""


def _fallback_merge(existing_items: list[dict], new_items: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}

    def make_key(item: dict) -> tuple:
        metadata = item.get("metadata", {}) or {}
        return (
            item.get("kind"),
            metadata.get("gid"),
            metadata.get("name"),
            item.get("content"),
        )

    for item in existing_items:
        merged[make_key(item)] = item

    for item in new_items:
        merged[make_key(item)] = item

    return list(merged.values())


@observe(as_type="generation")
async def memory_write_node(
        state: WorkflowState,
        memory_tool: MemoryTool,
        llm: LLMClient,
) -> dict:
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    memory_hits = state.get("memory_hits", "")
    final_answer = state.get("final_answer", "")
    user_query = state.get("user_query", "")
    is_eval = state.get("is_eval", False)
    prompt = _build_memory_merge_prompt(
        user_query=user_query,
        existing_items=memory_hits,
        final_answer=final_answer
    )

    merged_items: list[dict]

    try:
        result, data, latency = await llm.generate_json(
            prompt=prompt,
            fallback={"items": memory_hits},
        )
        merged_items = result.get("items", [])
        if not isinstance(merged_items, list):
            merged_items = memory_hits
    except Exception:
        merged_items = memory_hits
        data = {}
    if is_eval:
        merged_items = []
        return {
            "memory_write_queue": [],
            "session_memory": merged_items,
        }
    await memory_tool.write(
        user_id=user_id,
        session_id=session_id,
        payload=merged_items,
    )

    trace_tags = ["eval"] if is_eval else ["prod"]
    log_langfuse_generation(
        name="memory_write_node",
        response=data,
        model_input=prompt,
        latency_ms=latency,
        metadata={
            "session_id": state.get("session_id"),
            "memory_hits": merged_items,
        },
        tags=trace_tags
    )

    return {
        "memory_write_queue": [],
        "session_memory": merged_items,
    }
