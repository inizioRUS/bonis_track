from __future__ import annotations

from lib.multi_agent.state import WorkflowState
from lib.multi_agent.tools.memory import MemoryTool
from lib.observability.langfuse_utils import update_current_observation
from lib.observability.langfuse_utils import (
    observe,
    update_current_observation,
)
@observe(as_type="span")
async def memory_read_node(
        state: WorkflowState,
        memory_tool: MemoryTool,
) -> dict:
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")

    memory_hits = await memory_tool.get(session_id, user_id)

    update_current_observation(
        name="memory_read_node",
        metadata={
            "session_id": state.get("session_id"),
            "memory_hits": memory_hits,
        },
    )
    return {
        "memory_hits": memory_hits,
    }
