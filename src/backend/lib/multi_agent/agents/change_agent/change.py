from __future__ import annotations

from typing import Any

from lib.multi_agent.state import WorkflowState
from lib.multi_agent.tools.asana import AsanaTool
from lib.observability.langfuse_utils import (
    observe,
    update_current_observation,
)

ALLOWED_EXECUTION_TOOLS = {
    "asana.create_task",
    "asana.update_task",
    "asana.add_comment_to_task",
    "asana.create_section",
    "asana.add_task_to_section",
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
        if prev_sig == target and item.get("status") in {"success", "error"}:
            count += 1

    return count


def _extract_execution_steps(state: WorkflowState) -> list[dict[str, Any]]:
    plan = state.get("plan", {}) or {}


    execution_steps = plan.get("execution_steps")
    return execution_steps
@observe(as_type="span")
async def execution_node(
    state: WorkflowState,
    asana_tool: AsanaTool,
) -> dict:
    execution_steps = _extract_execution_steps(state)
    tool_history = list(state.get("tool_history", []))

    executed_steps: list[dict[str, Any]] = []

    for step in execution_steps:
        tool_name = step.get("tool")
        arguments = step.get("arguments", {}) or {}
        step_id = step.get("id", "")
        reason = step.get("reason", "")

        if tool_name not in ALLOWED_EXECUTION_TOOLS:
            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": "skipped",
                    "reason": f"Tool is not allowed in execution_node: {tool_name}",
                }
            )
            executed_steps.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "skipped",
                    "reason": "tool_not_allowed",
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
                    "reason": "Skipped repeated identical execution call",
                }
            )
            executed_steps.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "skipped",
                    "reason": "repeated_call",
                }
            )
            continue

        try:
            result: dict[str, Any] | None = None

            if tool_name == "asana.create_task":
                name = arguments.get("name")
                if not name:
                    raise ValueError("asana.create_task requires 'name'")

                result = await asana_tool.create_task(
                    name=name,
                    notes=arguments.get("notes"),
                    project_gid=arguments.get("project_gid"),
                    workspace_gid=arguments.get("workspace_gid"),
                    assignee_gid=arguments.get("assignee_gid"),
                    due_on=arguments.get("due_on"),
                    due_at=arguments.get("due_at"),
                    section_gid=arguments.get("section_gid"),
                    tags=arguments.get("tags"),
                    custom_fields=arguments.get("custom_fields"),
                )

            elif tool_name == "asana.update_task":
                task_gid = arguments.get("task_gid")
                if not task_gid:
                    raise ValueError("asana.update_task requires 'task_gid'")

                result = await asana_tool.update_task(
                    task_gid=task_gid,
                    name=arguments.get("name"),
                    notes=arguments.get("notes"),
                    assignee_gid=arguments.get("assignee_gid"),
                    completed=arguments.get("completed"),
                    due_on=arguments.get("due_on"),
                    due_at=arguments.get("due_at"),
                    custom_fields=arguments.get("custom_fields"),
                )

            elif tool_name == "asana.add_comment_to_task":
                task_gid = arguments.get("task_gid")
                text = arguments.get("text")
                if not task_gid:
                    raise ValueError("asana.add_comment_to_task requires 'task_gid'")
                if not text:
                    raise ValueError("asana.add_comment_to_task requires 'text'")

                result = await asana_tool.add_comment_to_task(
                    task_gid=task_gid,
                    text=text,
                )

            elif tool_name == "asana.create_section":
                name = arguments.get("name")
                if not name:
                    raise ValueError("asana.create_section requires 'name'")

                result = await asana_tool.create_section(
                    project_gid=arguments.get("project_gid"),
                    name=name,
                )

            elif tool_name == "asana.add_task_to_section":
                task_gid = arguments.get("task_gid")
                section_gid = arguments.get("section_gid")
                if not task_gid:
                    raise ValueError("asana.add_task_to_section requires 'task_gid'")
                if not section_gid:
                    raise ValueError("asana.add_task_to_section requires 'section_gid'")

                result = await asana_tool.add_task_to_section(
                    task_gid=task_gid,
                    section_gid=section_gid,
                )





            tool_history.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    "arguments": arguments,
                    'result': result,
                    "status": "success",
                }
            )
            executed_steps.append(
                {
                    "step_id": step_id,
                    "tool": tool_name,
                    'result': result,
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


    state["plan"]["execution_steps"] = []
    is_eval = state.get("is_eval", False)
    trace_tags = ["eval"] if is_eval else ["prod"]
    update_current_observation(
        name="execution_node",
        metadata={
            "session_id": state.get("session_id"),
            "executed_steps": executed_steps,
            "iteration": state.get("iteration") + 1,
        },
        tags=trace_tags
    )

    return {
        "tool_history": tool_history,
        "last_executed_steps": executed_steps,
        "iteration": state.get("iteration", 0) + 1,
    }