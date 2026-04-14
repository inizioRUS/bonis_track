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
    log_eval_scores,
)


def compute_retrieval_metrics(
        final_sources: list[dict],
        expected_doc_ids: list[str],
) -> dict[str, float]:
    if not expected_doc_ids:
        return {}

    retrieved_doc_ids: list[str] = []
    for source in final_sources:
        doc_id = source.get("url")
        if doc_id:
            retrieved_doc_ids.append(str(doc_id))

    if not retrieved_doc_ids:
        return {
            "hit_at_10": 0.0,
            "recall_at_10": 0.0,
            "mrr_at_10": 0.0,
        }

    expected_set = {str(doc_id) for doc_id in expected_doc_ids}

    hit_at_10 = 1.0 if any(doc_id in expected_set for doc_id in retrieved_doc_ids[:10]) else 0.0

    found_relevant = [doc_id for doc_id in retrieved_doc_ids[:10] if doc_id in expected_set]
    recall_at_10 = len(set(found_relevant)) / max(len(expected_set), 1)

    mrr_at_10 = 0.0
    for rank, doc_id in enumerate(retrieved_doc_ids[:10], start=1):
        if doc_id in expected_set:
            mrr_at_10 = 1.0 / rank
            break

    return {
        "hit_at_10": hit_at_10,
        "recall_at_10": recall_at_10,
        "mrr_at_10": mrr_at_10,
    }


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
            memory_tool=self.memory_tool,
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
            is_eval: bool = False,
            expected_doc_ids: list[str] | None = None,
            history: list[dict[str, str]] | None = None,
    ) -> dict:
        trace_tags = ["eval"] if is_eval else ["prod"]
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
            "is_eval": is_eval,
            "expected_doc_ids": expected_doc_ids or [],
        }
        trace_tags = ["eval"] if is_eval else ["prod"]
        update_current_observation(
            name="workflow.run",
            input_data={"query": query[:500]},
            metadata={
                "session_id": session_id,
                "user_hash": anonymize_user_id(user_id),
                "deep_research": deep_research,
                "is_eval": is_eval,
                "expected_doc_ids_count": len(expected_doc_ids or []),
            },
            tags=trace_tags,
        )

        result = await self.graph.ainvoke(initial_state, config={"recursion_limit":50})

        final_sources = result.get("final_sources", [])

        if is_eval:
            metrics = compute_retrieval_metrics(
                final_sources=final_sources,
                expected_doc_ids=expected_doc_ids or []
            )
            if metrics:
                log_eval_scores(
                    metrics,
                    comment="retrieval eval based on final_sources",
                    tags=trace_tags,
                )

        update_current_observation(
            output_data={
                "iteration": result.get("iteration", 0),
                "has_final_answer": bool(result.get("final_answer")),
                "final_sources_count": len(final_sources),
                "is_eval": is_eval,
            },
            tags=trace_tags,
        )

        flush_langfuse(trace_tags)
        return result
