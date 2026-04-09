from __future__ import annotations

from typing import Any

from lib.multi_agent.state import WorkflowState
from lib.multi_agent.tools.asana import AsanaTool
from lib.multi_agent.tools.habr import HabrTool
from lib.multi_agent.tools.retriever import RetrieverTool
from lib.observability.langfuse_utils import (
    observe,
    update_current_observation,
)

ALLOWED_RETRIEVAL_TOOLS = {
    "retriever.search",
    "asana.get_me",
    "asana.get_workspaces",
    "asana.search_tasks",
    "asana.get_project_tasks",
    "asana.get_task",
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


@observe(as_type="generation")
async def iterative_retrieval_node(
    state: WorkflowState,
    retriever_tool: RetrieverTool,
    asana_tool: AsanaTool,
    habr_tool: HabrTool,
) -> dict:
    print(state)
    plan = state.get("plan", {})
    steps = plan.get("steps", [])

    retrieval_results = list(state.get("retrieval_results", []))
    evidence = list(state.get("evidence", []))
    tool_history = list(state.get("tool_history", []))

    executed_steps: list[dict[str, Any]] = []

    for step in steps:
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

                result = await retriever_tool.search(
                    query=query,
                    top_k=arguments.get("top_k"),
                    candidate_k=arguments.get("candidate_k"),
                    doc_id=arguments.get("doc_id"),
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

            elif tool_name == "asana.search_tasks":
                text = arguments.get("text")
                if not text and text != '':
                    raise ValueError("asana.search_tasks requires 'text'")

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

    plan["steps"] = []
    update_current_observation(
        name="retrieval_node",
        metadata={
            "session_id": state.get("session_id"),
            "executed_steps": executed_steps,
            "iteration": state.get("iteration", 0) + 1,
        },
    )

    return {
        "retrieval_results": retrieval_results,
        "tool_history": tool_history,
        "iteration": state.get("iteration", 0) + 1,
        "last_executed_steps": executed_steps,
        "evidence": evidence,
        "plan": plan
    }