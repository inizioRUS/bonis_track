from __future__ import annotations

from lib.multi_agent.state import WorkflowState


async def orchestrator_node(state: WorkflowState) -> dict:
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 8)
    plan = state.get("plan", {})
    print(plan)
    steps = plan.get("steps", [])
    execution_steps = plan.get("execution_steps", [])
    next_agent = state.get("next_agent", "agent")
    if state.get("final_answer"):
        next_agent = "END"

    elif iteration >= max_iterations or next_agent == "writer_agent":
        next_agent = "writer_agent"


    elif not plan or next_agent == "planner_agent":
        next_agent = "planner_agent"

    elif len(steps) > 0:
        next_agent = "retrieval_agent"
    elif len(execution_steps) > 0:
        next_agent = "execution_agent"

    else:
        next_agent = "verifier_agent"

    return {"next_agent": next_agent}
