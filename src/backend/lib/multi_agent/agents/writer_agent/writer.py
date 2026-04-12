from __future__ import annotations
import time
from lib.multi_agent.state import WorkflowState
from lib.llm.llm_client_open_router import LLMClient
from lib.observability.langfuse_utils import (
    observe,
    log_langfuse_generation,
)


@observe(as_type="generation")
async def writer_node(state: WorkflowState, llm: LLMClient) -> dict:
    prompt = f"""
Ты writer agent.
Сформируй финальный ответ пользователю.

Используй:
user_query = {state["user_query"]}
analysis = {state.get("analysis", {})}
plan = {state.get("plan", {})}
verification = {state.get("verification", {})}
tool_history = {state.get("tool_history", [])}
retrieval_results = {state.get("retrieval_results", [])}

Если данных не хватает, честно скажи об этом.
"""

    final_answer, data, latency = await llm.generate_text(prompt)
    final_sources: list[dict] = []
    was_id = set()

    for item in state.get("evidence", []):
        if item["type"] == "retriever_search":
            hits = item.get("hits", [])
            for hit in hits:
                meta = hit.get("metadata", {})
                if meta.get("url") not in was_id:
                    final_sources.append(
                        {
                            "source": "retriever",
                            "title": meta.get("title"),
                            "url": meta.get("url"),
                            "doc_id": hit.get("doc_id"),
                        }
                    )
                    was_id.add(meta.get("url"))

        elif item["type"] == "habr_article":
            if item.get("url") not in was_id:
                final_sources.append(
                    {
                        "source": "habr",
                        "title": item.get("title"),
                        "url": item.get("url"),
                    }
                )
                was_id.add(item.get("url"))
        elif item["type"] == "asana":
            article = item.get("result", {})
            if article.get("url") not in was_id:
                final_sources.append(
                    {
                        "source": "asana",
                        "title": article.get("title"),
                        "url": article.get("url"),
                    }
                )
                was_id.add(article.get("url"))
    is_eval = state.get("is_eval", False)
    trace_tags = ["eval"] if is_eval else ["prod"]
    log_langfuse_generation(
        name="writer_node",
        response=data,
        model_input=prompt,
        latency_ms=latency,
        metadata={
            "session_id": state.get("session_id"),
            "final_answer": final_answer,
            "final_sources": final_sources,
            "iteration": state.get("iteration", 0) + 1,
        },
        tags=trace_tags
    )
    return {
        "final_answer": final_answer,
        "final_sources": final_sources,
        "iteration": state.get("iteration", 0) + 1,
    }
