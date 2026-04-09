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
    print(state.get("evidence"))
    final_answer, data, latency = await llm.generate_text(prompt)
    final_sources: list[dict] = []
    print(state.get("evidence"))
    for item in state.get("evidence", []):
        if item["type"] == "retriever_search":
            hits = item.get("hits", [])
            for hit in hits:
                meta = hit.get("metadata", {})
                final_sources.append(
                    {
                        "source": "retriever",
                        "title": meta.get("title"),
                        "url": meta.get("url"),
                        "doc_id": hit.get("doc_id"),
                    }
                )
        elif item["type"] == "habr_article":
            final_sources.append(
                {
                    "source": "habr",
                    "title": item.get("title"),
                    "url": item.get("url"),
                }
            )
        elif item["type"] == "asana":
            article = item.get("result", {})
            final_sources.append(
                {
                    "source": "asana",
                    "title": article.get("title"),
                    "url": article.get("url"),
                }
            )

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
    )
    return {
        "final_answer": final_answer,
        "final_sources": final_sources,
        "iteration": state.get("iteration", 0) + 1,
    }
