from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


SearchMode = Literal["vector", "bm25", "hybrid"]


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    candidate_k: int = 30
    doc_id: Optional[str] = None
    search_mode: SearchMode = "hybrid"


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Any]
    retrieval_mode: SearchMode
    retrieval_score: float
    rerank_score: float


class SearchResponse(BaseModel):
    query: str
    search_mode: SearchMode
    hits: List[SearchHit]