from typing import Any

import httpx

from src.shared.config import settings
from src.state.models import Evidence


class RetrieverClient:
    async def search(self, query: str, top_k: int | None = None) -> list[Evidence]:
        payload = {
            "query": query,
            "top_k": top_k or settings.retriever_top_k,
            "mode": "hybrid",
        }

        async with httpx.AsyncClient(timeout=settings.request_timeout_sec) as client:
            response = await client.post(settings.retriever_url, json=payload)
            response.raise_for_status()
            data = response.json()

        items: list[dict[str, Any]] = data.get("items", [])
        evidences: list[Evidence] = []

        for item in items:
            evidences.append(
                Evidence(
                    source=item.get("source", "retriever"),
                    text=item.get("text", ""),
                    title=item.get("title"),
                    url=item.get("url"),
                    score=item.get("score"),
                    metadata=item.get("metadata", {}),
                )
            )

        return evidences