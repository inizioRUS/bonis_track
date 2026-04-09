from __future__ import annotations

from core.config import settings
from lib.llm.llm_client_open_router import LLMClient
from lib.multi_agent.graph import build_graph
from lib.multi_agent.tools.asana import AsanaTool
from lib.multi_agent.tools.habr import HabrTool
from lib.multi_agent.tools.retriever import RetrieverTool
from lib.multi_agent.tools.memory import MemoryTool
from lib.observability.langfuse_utils import (
    observe,
    anonymize_user_id,
    update_current_observation,
    flush_langfuse,
)


class RAGWorkflow:
    def __init__(self, redis_metadata, asana_api_key) -> None:
        self.llm = LLMClient()
        self.retriever_tool = RetrieverTool()
        self.asana_tool = AsanaTool(asana_api_key)
        self.habr_tool = HabrTool()

        self.memory_tool = MemoryTool(redis_metadata)

        self.graph = build_graph(
            llm=self.llm,
            retriever_tool=self.retriever_tool,
            asana_tool=self.asana_tool,
            habr_tool=self.habr_tool,
            memory_tool=self.memory_tool
        )

    @observe(as_type="trace")
    async def run(
            self,
            *,
            session_id: str,
            user_id: str,
            username: str,
            query: str,
            deep_research: bool,
            redis_client,
            history: list[dict[str, str]] | None = None,
    ) -> dict:
        initial_state = {
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "user_query": query,
            "deep_research": deep_research,
            "messages": history or [],
            "iteration": 0,
            "max_iterations": settings.max_cycle_steps,
            "retrieval_queries": [],
            "retrieval_results": [],
            "asana_results": [],
            "habr_articles": [],
            "evidence": [],
            "final_sources": [],
        }
        update_current_observation(
            name="workflow.run",
            input_data={"query": query[:500]},
            metadata={
                "session_id": session_id,
                "user_hash": anonymize_user_id(user_id),
                "deep_research": deep_research,
            },
        )

        result = await self.graph.ainvoke(initial_state)

        update_current_observation(
            output_data={
                "iteration": result.get("iteration", 0),
                "has_final_answer": bool(result.get("final_answer")),
                "final_sources_count": len(result.get("final_sources", [])),
            }
        )

        flush_langfuse()
        return result
