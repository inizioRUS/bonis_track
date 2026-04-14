from __future__ import annotations

from lib.multi_agent.state import WorkflowState
from lib.llm.llm_client_open_router import LLMClient
from lib.observability.langfuse_utils import (
    observe,
    log_langfuse_generation,
)


@observe(as_type="generation")
async def verifier_node(state: WorkflowState, llm: LLMClient) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 5)

    system_prompt = """
You are the Verifier Agent in a multi-agent workflow.

Your job is to evaluate whether the currently collected information is sufficient and reliable enough for the next step.

You must review the full state and decide:
1. whether more retrieval or planning is needed,
2. whether the system is ready to write the final response,
3. whether an external action / production change is needed,
4. whether there are unresolved gaps or weak evidence,
5. which agent should act next.

Rules:
- Be strict about factual sufficiency, but do not request more retrieval if the current evidence is already enough.
- Prefer moving forward instead of causing unnecessary loops.
- If the evidence covers the user query well enough, mark it ready for final response.
- If there is enough information to perform a requested external action, mark that tool execution is needed.
- If evidence is weak, contradictory, missing critical facts, or does not answer the actual user query, request more retrieval or replanning.
- If iteration is close to the limit, prefer finalizing with explicit caveats rather than looping again.
- Never output explanatory text outside JSON.
""".strip()

    prompt = f"""
Evaluate the current workflow state.

Current state:
user_query = {state.get("user_query", "")}
plan = {state.get("plan", {})}
retrieval_results = {state.get("retrieval_results", [])}
tool_history = {state.get("tool_history", [])[-10:]}
iteration = {iteration}
max_iterations = {max_iterations}

Return JSON with exactly these fields:
- verdict: string
- confidence: number
- needs_more_retrieval: boolean
- needs_replanning: boolean
- ready_for_final_response: boolean
- needs_tool_execution: boolean
- execution_actions: list of strings
- unresolved_gaps: list of strings
- notes: list of strings
- next_agent: string[planner_agent, writer_agent]
""".strip()

    retrieval_results = state.get("retrieval_results", [])

    near_limit = iteration + 1 >= max_iterations

    verification, data, latency = await llm.generate_json(
        prompt=prompt,
        fallback={},
        system_prompt=system_prompt,
    )
    stalled = False
    # Hard guards against looping
    if near_limit or stalled:
        verification["needs_more_retrieval"] = False
        verification["needs_replanning"] = False

        if not verification.get("ready_for_final_response", False):
            verification["ready_for_final_response"] = True

        if verification.get("needs_tool_execution", False):
            # if you do not yet have execution_agent, route back to writer for now
            verification["next_agent"] = "writer_agent"
            verification.setdefault("notes", []).append(
                "Tool execution was requested, but workflow is stopping due to limits."
            )
        else:
            verification["next_agent"] = "writer_agent"
    else:
        next_agent = verification.get("next_agent")
        if not next_agent:
            if verification.get("needs_tool_execution", False):
                next_agent = "execution_agent"
            elif verification.get("ready_for_final_response", False):
                next_agent = "writer_agent"
            elif verification.get("needs_more_retrieval", False) or verification.get("needs_replanning", False):
                next_agent = "planner_agent"
            else:
                next_agent = "writer_agent"
            verification["next_agent"] = next_agent
    is_eval = state.get("is_eval", False)
    trace_tags = ["eval"] if is_eval else ["prod"]
    log_langfuse_generation(
        name="verifier_node",
        response=data,
        model_input=prompt,
        latency_ms=latency,
        metadata={
            "session_id": state.get("session_id"),
            "memory_hits": verification,
            "iteration": iteration + 1,
        },
        tags=trace_tags
    )
    return {
        "verification": verification,
        "iteration": iteration + 1,
        "next_agent": verification.get("next_agent", "writer_agent"),
    }
