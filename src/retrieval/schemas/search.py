from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    candidate_k: int = 30
    doc_id: Optional[str] = None


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Any]
    vector_score: float
    rerank_score: float


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]