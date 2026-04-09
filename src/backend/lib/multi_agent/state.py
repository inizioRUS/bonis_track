from typing import Any, Optional
from typing_extensions import TypedDict


class MemoryItem(TypedDict, total=False):
    id: str
    kind: str              # "user_pref" | "project_fact" | "task_context" | "summary" | ...
    content: str
    source: str            # "session" | "asana" | "retriever" | "llm"
    score: float
    metadata: dict[str, Any]


class WorkflowState(TypedDict, total=False):
    session_id: str
    user_id: str
    username: str
    user_query: str
    deep_research: bool

    messages: list[dict[str, str]]

    plan: dict[str, Any]

    tool_history: list[dict[str, Any]]
    retrieval_results: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    verification: dict[str, Any]
    next_agent: str
    final_answer: Optional[str]
    final_sources: list[dict[str, Any]]

    iteration: int
    max_iterations: int

    # memory
    memory_hits: list[MemoryItem]        # что достали из долговременной памяти