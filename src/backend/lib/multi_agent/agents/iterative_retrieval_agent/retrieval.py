from __future__ import annotations

import json
from typing import Any

from lib.multi_agent.state import WorkflowState
from lib.multi_agent.tools.asana import AsanaTool
from lib.multi_agent.tools.habr import HabrTool
from lib.multi_agent.tools.retriever import RetrieverTool
from lib.observability.langfuse_utils import (
    observe,
    update_current_observation,
    log_langfuse_generation,
    create_generation
)

from lib.llm.llm_client_open_router import LLMClient

ALLOWED_RETRIEVAL_TOOLS = {
    "retriever.search",
    "asana.get_me",
    "asana.get_workspaces",
    "asana.search_tasks",
    "asana.get_project_tasks",
    "asana.get_task",
    "asana.get_project_members",
    "asana.get_workspace_users",
    "asana.get_task_stories",
    "asana.get_projects",
    "asana.get_project",
    "asana.get_sections",
    "habr.get_article_text",
}


def _normalize_arguments(arguments: dict[str, Any]) -> tuple:
    normalized_items = []
    for key, value in sorted(arguments.items()):
        if isinstance(value, list):
            value = tuple(value)
        elif isinstance(value, dict):
            value = tuple(sorted(value.items()))
        normalized_items.append((key, value))
    return tuple(normalized_items)


def _tool_call_signature(tool: str, arguments: dict[str, Any]) -> tuple:
    return tool, _normalize_arguments(arguments)


def _count_same_tool_call(
        tool_history: list[dict[str, Any]],
        tool: str,
        arguments: dict[str, Any],
) -> int:
    target = _tool_call_signature(tool, arguments)
    count = 0

    for item in tool_history:
        prev_tool = item.get("tool")
        prev_args = item.get("arguments", {})
        prev_sig = _tool_call_signature(prev_tool, prev_args)
        if prev_sig == target:
            count += 1

    return count


def _safe_json_dump(data: Any, max_len: int = 12000) -> str:
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text[:max_len]


async def _rewrite_remaining_steps_with_llm(
        llm: LLMClient,
        state: WorkflowState,
        remaining_steps: list[dict[str, Any]],
        executed_steps: list[dict[str, Any]],
        tool_history: list[dict[str, Any]],
        retrieval_results: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Rewrites only the remaining steps.
    Guarantees after sanitization:
    - same number of steps as input
    - original step ids are preserved
    - only allowed tools remain
    - fallback to original remaining_steps on invalid LLM output
    """
    if not remaining_steps:
        return remaining_steps

    user_goal = (
            state.get("user_query")
            or state.get("question")
            or state.get("task")
            or state.get("input")
            or ""
    )

    fallback = {"steps": remaining_steps}

    prompt = f"""
You are a planning assistant for a retrieval workflow.

Your task is to rewrite ONLY the remaining plan steps based on the results of previously executed steps.

Important rules:
1. You may modify only the remaining steps.
2. You must return the EXACT SAME NUMBER of steps as provided in "remaining_steps".
3. Do NOT add new steps.
4. Do NOT remove steps.
5. You may change only:
   - "tool"
   - "arguments"
   - "reason"
6. Keep each step's "id" unchanged.
7. Use ONLY allowed tools.
8. Avoid repeating identical tool calls unless truly necessary.
9. If a step is already good, keep it unchanged.
10. Return valid JSON only. No markdown. No explanations.

Allowed tools:
{sorted(ALLOWED_RETRIEVAL_TOOLS)}

User goal:
{user_goal}

Already executed steps:
{_safe_json_dump(executed_steps, max_len=3000)}

Tool history:
{_safe_json_dump(tool_history, max_len=5000)}

Recent retrieval results:
{_safe_json_dump(retrieval_results[-5:], max_len=6000)}

Recent evidence:
{_safe_json_dump(evidence[-5:], max_len=4000)}

Remaining steps to rewrite:
{_safe_json_dump(remaining_steps, max_len=5000)}

Return JSON only in this format:
{{
  "steps": [
    {{
      "id": "original step id",
      "tool": "allowed tool name",
      "arguments": {{}},
      "reason": "updated reason"
    }}
  ]
}}
""".strip()

    parsed, data, latency = await llm.generate_json(
        prompt=prompt,
        fallback=fallback,
        system_prompt=(
            "You rewrite future retrieval plan steps. "
            "Return strict JSON only. "
            "Do not add steps. "
            "Do not remove steps. "
            "Do not change step ids."
        ),
    )

    new_steps = parsed.get("steps", [])
    if not isinstance(new_steps, list):
        return remaining_steps

    if len(new_steps) != len(remaining_steps):
        return remaining_steps

    sanitized_steps: list[dict[str, Any]] = []

    for original_step, new_step in zip(remaining_steps, new_steps):
        if not isinstance(new_step, dict):
            sanitized_steps.append(original_step)
            continue

        tool_name = new_step.get("tool", original_step.get("tool"))
        if tool_name not in ALLOWED_RETRIEVAL_TOOLS:
            tool_name = original_step.get("tool")

        arguments = new_step.get("arguments", original_step.get("arguments", {}))
        if not isinstance(arguments, dict):
            arguments = original_step.get("arguments", {}) or {}

        reason = new_step.get("reason", original_step.get("reason", ""))
        if not isinstance(reason, str):
            reason = original_step.get("reason", "")

        sanitized_steps.append(
            {
                "id": original_step.get("id", ""),
                "tool": tool_name,
                "arguments": arguments,
                "reason": reason,
            }
        )

    return sanitized_steps, data, latency


@observe(as_type="generation")
async def iterative_retrieval_node(
        state: WorkflowState,
        retriever_tool: RetrieverTool,
        asana_tool: AsanaTool,
        habr_tool: HabrTool,
        llm: LLMClient,
) -> dict:
    is_eval = state.get("is_eval", False)
    trace_tags = ["eval"] if is_eval else ["prod"]
    plan = state.get("plan", {})
    steps = list(plan.get("steps", []))

    retrieval_results = list(state.get("retrieval_results", []))
    evidence = list(state.get("evidence", []))
    tool_history = list(state.get("tool_history", []))

    executed_steps: list[dict[str, Any]] = []

    for idx, step in enumerate(steps):
        tool_name = step.get("tool")
        arguments = step.get("arguments", {}) or {}
        step_id = step.get("id", "")
        reason = step.get("reason", "")

        if tool_name not in ALLOWED_RETRIEVAL_TOOLS:
            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": "skipped",
                    "reason": f"Tool is not allowed in iterative_retrieval_node: {tool_name}",
                }
            )
            continue

        repeated_count = _count_same_tool_call(tool_history, tool_name, arguments)
        if repeated_count >= 2:
            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": "skipped",
                    "reason": "Skipped repeated identical tool call",
                }
            )
            continue

        try:
            result: dict[str, Any] | None = None

            if tool_name == "retriever.search":
                query = arguments.get("query")

                if not query:
                    raise ValueError("retriever.search requires 'query'")
                try:
                    result = await retriever_tool.search(
                        query=query,
                        top_k=arguments.get("top_k"),
                        candidate_k=arguments.get("candidate_k"),
                        doc_id=arguments.get("doc_id"),
                    )
                except Exception as e:
                    print(f"Failed vector search with error {str(e)[:200]} change to bm25")
                    result = await retriever_tool.search(
                        query=query,
                        top_k=arguments.get("top_k"),
                        candidate_k=arguments.get("candidate_k"),
                        doc_id=arguments.get("doc_id"),
                        search_mode="bm25",
                    )
                result["type"] = "retriever_search"
                retrieval_results.append(result)
                evidence.append(result)

            elif tool_name == "asana.get_me":
                result = await asana_tool.get_me()
                retrieval_results.append(result)

            elif tool_name == "asana.get_workspaces":
                result = await asana_tool.get_workspaces()
                retrieval_results.append(result)

            elif tool_name == "asana.get_project_members":
                result = await asana_tool.get_project_members(
                    project_gid=arguments.get("project_gid"),
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset"),
                    opt_fields=arguments.get("opt_fields"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.get_workspace_users":
                result = await asana_tool.get_workspace_users(
                    workspace_gid=arguments.get("workspace_gid"),
                    limit=arguments.get("limit"),
                    offset=arguments.get("offset"),
                    opt_fields=arguments.get("opt_fields"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.search_tasks":
                text = arguments.get("text")
                if not text and text != "":
                    text = ""

                result = await asana_tool.search_tasks(
                    text=text,
                    workspace_gid=arguments.get("workspace_gid"),
                    project_gid=arguments.get("project_gid"),
                    completed=arguments.get("completed"),
                    assignee_gid=arguments.get("assignee_gid"),
                    limit=arguments.get("limit"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.get_project_tasks":
                result = await asana_tool.get_project_tasks(
                    project_id=arguments.get("project_id"),
                    completed_since=arguments.get("completed_since"),
                    limit=arguments.get("limit"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.get_task":
                task_gid = arguments.get("task_gid")
                if not task_gid:
                    raise ValueError("asana.get_task requires 'task_gid'")

                result = await asana_tool.get_task(
                    task_gid=task_gid,
                    opt_fields=arguments.get("opt_fields"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.get_task_stories":
                task_gid = arguments.get("task_gid")
                if not task_gid:
                    raise ValueError("asana.get_task_stories requires 'task_gid'")

                result = await asana_tool.get_task_stories(task_gid=task_gid)
                retrieval_results.append(result)

            elif tool_name == "asana.get_projects":
                result = await asana_tool.get_projects(
                    workspace_gid=arguments.get("workspace_gid"),
                    team_gid=arguments.get("team_gid"),
                    archived=arguments.get("archived"),
                )
                retrieval_results.append(result)

            elif tool_name == "asana.get_project":
                project_gid = arguments.get("project_gid")
                if not project_gid:
                    raise ValueError("asana.get_project requires 'project_gid'")

                result = await asana_tool.get_project(project_gid=project_gid)
                retrieval_results.append(result)

            elif tool_name == "asana.get_sections":
                result = await asana_tool.get_sections(
                    project_gid=arguments.get("project_gid")
                )
                retrieval_results.append(result)

            elif tool_name == "habr.get_article_text":
                url = arguments.get("url")
                if not url:
                    raise ValueError("habr.get_article_text requires 'url'")

                result = await habr_tool.get_article_text(url)
                result["type"] = "habr_article"
                evidence.append(result)
                retrieval_results.append(result)

            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": "success",
                    "reason": reason,
                }
            )
            executed_steps.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "success",
                }
            )

        except Exception as exc:
            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": "error",
                    "error": str(exc),
                    "reason": reason,
                }
            )
            executed_steps.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "error",
                    "error": str(exc),
                }
            )

        remaining_steps = steps[idx + 1:]
        if remaining_steps:
            try:
                with create_generation(
                        name=f"rewrite_remaining_steps_{idx}",
                        model_input={"remaining_steps": remaining_steps},
                        metadata={"step_index": idx},
                        tags=trace_tags,
                ):
                    rewritten_steps, data, latency = await _rewrite_remaining_steps_with_llm(
                        llm=llm,
                        state=state,
                        remaining_steps=remaining_steps,
                        executed_steps=executed_steps,
                        tool_history=tool_history,
                        retrieval_results=retrieval_results,
                        evidence=evidence,
                    )
                    if len(rewritten_steps) == len(remaining_steps):
                        steps[idx + 1:] = rewritten_steps

                    log_langfuse_generation(
                        name=f"rewrite_remaining_steps_{idx}",
                        model_input={"remaining_steps": remaining_steps},
                        response=data,
                        latency_ms=latency,
                        metadata={"step_index": idx},
                        tags=trace_tags,
                    )
            except Exception as e:
                print(e)
    plan["steps"] = []

    execution_steps = plan.get("execution_steps", [])
    if execution_steps:
        try:
            with create_generation(
                    name=f"rewrite_remaining_steps_exc",
                    model_input={"remaining_steps": execution_steps},
                    metadata={"step_index": "exc"},
                    tags=trace_tags,
            ):
                rewritten_steps, data, latency = await _rewrite_remaining_steps_with_llm(
                    llm=llm,
                    state=state,
                    remaining_steps=execution_steps,
                    executed_steps=executed_steps,
                    tool_history=tool_history,
                    retrieval_results=retrieval_results,
                    evidence=evidence,
                )
                if len(rewritten_steps) == len(execution_steps):
                    execution_steps = rewritten_steps

                log_langfuse_generation(
                    name=f"rewrite_remaining_steps_exc",
                    model_input={"remaining_steps": execution_steps},
                    response=data,
                    latency_ms=latency,
                    metadata={"step_index": "exc"},
                    tags=trace_tags,
                )
        except:
            pass

    update_current_observation(
        name="retrieval_node",
        metadata={
            "session_id": state.get("session_id"),
            "executed_steps": executed_steps,
            "iteration": state.get("iteration", 0) + 1,
        },
        tags=trace_tags,
    )
    plan["execution_steps"] = execution_steps
    return {
        "retrieval_results": retrieval_results,
        "tool_history": tool_history,
        "iteration": state.get("iteration", 0) + 1,
        "last_executed_steps": executed_steps,
        "evidence": evidence,
        "plan": plan,
    }
