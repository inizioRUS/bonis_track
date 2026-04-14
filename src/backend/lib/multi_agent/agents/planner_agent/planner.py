from __future__ import annotations

from lib.multi_agent.state import WorkflowState
from lib.llm.llm_client_open_router import LLMClient
from lib.observability.langfuse_utils import (
    observe,
    log_langfuse_generation,
)

@observe(as_type="generation")
async def planner_node(state: WorkflowState, llm: LLMClient) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 10)

    prompt = f"""
You are the Planner Agent in a multi-agent workflow.

Your job is to create an execution plan for the NEXT iteration of work, not to write the final answer.

You must decide:
1. what information is still missing,
2. which tools should be used next,
3. in what order they should be used,
4. what exact tool arguments should be passed,
5. when a tool call should be skipped to avoid redundant work.

You have access to two categories of tools:

--- RETRIEVAL TOOLS (read-only, used for gathering information) ---
1. retriever.search(query, top_k?, candidate_k?, doc_id?)
2. habr.get_article_text(url)
3. asana.get_me()
4. asana.get_workspaces()
5. asana.get_projects(workspace_gid, team_gid?, archived?)
6. asana.get_project(project_gid)
7. asana.get_project_members(project_gid?, limit?, offset?, opt_fields?)
8. asana.get_workspace_users(workspace_gid, limit?, offset?, opt_fields?)
9. asana.get_project_tasks(project_id?, completed_since?, limit?)
10. asana.get_task(task_gid, opt_fields?)
11. asana.search_tasks(text, workspace_gid, project_gid?, completed?, assignee_gid?, limit?)
12. asana.get_task_stories(task_gid)
13. asana.get_sections(project_gid?)

* task_gid,project_id,team_gid, assignee_gid - it's always numeric

* habr url always should views like https://habr.com/ru/articles/<id>/

--- EXECUTION TOOLS (write operations, cause side effects) ---
1. asana.create_task(name, notes?, project_gid?, workspace_gid?, assignee_gid?, due_on?, due_at?, section_gid?, tags?, custom_fields?)
2. asana.update_task(task_gid, name?, notes?, assignee_gid?, completed?, due_on?, due_at?, custom_fields?)
3. asana.add_comment_to_task(task_gid, text)
4. asana.create_section(project_gid?, name)
5. asana.add_task_to_section(task_gid, section_gid)

task_gid,project_id,team_gid, assignee_gid - it's always numeric

Rules:
- Separate retrieval steps and execution steps.
- Use retrieval tools to gather missing information.
- Use execution tools ONLY if there is enough information to safely perform the action.
- Do NOT mix retrieval and execution steps in the same list.
- Prefer the minimum number of tool calls needed to make progress.
- Do not repeat tool calls that have already been done unless there is a strong reason.
- Use the current state to avoid redundant or cyclic planning.
- If enough evidence already exists, do not plan more retrieval.
- If the user query is about internal tasks, projects, statuses, assignees, deadlines, comments, or project structure, prefer Asana tools.
- If the query is about documents, internal knowledge, or semantic search, prefer retriever.search.
- If a relevant Habr URL is already known and article text has not been downloaded yet, use habr.get_article_text.
- If critical facts are still missing, propose no more than 20 retrieval tool calls in one plan iteration.
- Execution steps must be precise and safe (never guess IDs or critical fields).
- If the workflow is close to completion, say that no more tool calls are needed.
- Never invent tool names.
- Never output explanatory text outside JSON.
- retriever.search its more about search documents or extra context exclude tasks
- you can't make equals requests
- always first use asana.get_me(), asana.get_workspaces() for asana task


Current state:
user_query = {state.get("user_query", "")}
existing_plan = {state.get("plan", {})}
retrieval_results = {state.get("retrieval_results", [])}
messages history= {state.get("messages", [])}
memory_hits= {state.get("memory_hits", [])}

Return JSON with exactly these fields:
- goal: string
- strategy: string
- tool_calls_needed: boolean
- steps: list of objects (RETRIEVAL ONLY), where each object has:
  - id: string
  - tool: string
  - reason: string
  - arguments: object
  - expected_output: string
  - success_criteria: string
- execution_steps: list of objects (EXECUTION ONLY), where each object has:
  - id: string
  - tool: string
  - reason: string
  - arguments: object
  - expected_output: string
  - success_criteria: string
- completion_criteria: list of strings
"""


    plan, data, latency = await llm.generate_json(prompt,fallback={})

    # hard guard against runaway planning near the iteration limit
    if iteration + 1 >= max_iterations:
        plan["tool_calls_needed"] = False
        plan["steps"] = []
        if not plan.get("completion_criteria"):
            plan["completion_criteria"] = ["Stop tool usage and prepare final response"]
    is_eval = state.get("is_eval", False)
    trace_tags = ["eval"] if is_eval else ["prod"]
    log_langfuse_generation(
        name="planner_node",
        response=data,
        model_input=prompt,
        latency_ms=latency,
        metadata={
            "session_id": state.get("session_id"),
            "memory_hits": plan
        },
        tags=trace_tags
    )

    return {
        "plan": plan,
        "iteration": iteration + 1,
        "next_agent": ""
    }