from __future__ import annotations

import httpx

from core.config import settings


class RetrieverTool:
    def __init__(self) -> None:
        self.base_url = settings.retriever_url.rstrip("/")
        self.timeout = settings.request_timeout_sec

    async def search(
            self,
            query: str,
            top_k: int | None = None,
            candidate_k: int | None = None,
            doc_id: str | None = None,
            search_mode: str = "hybrid"
    ) -> dict:
        payload: dict = {
            "query": query,
            "top_k": top_k or settings.retriever_top_k,
            "candidate_k": candidate_k or settings.retriever_candidate_k,
            "search_mode": search_mode
        }
        if doc_id:
            payload["doc_id"] = doc_id

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/search", json=payload)
            response.raise_for_status()
            return response.json()
