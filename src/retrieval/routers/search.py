from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import (
    get_embedding_service,
    get_qdrant_service,
    get_reranker_service,
    get_sparse_embedding_service,
)
from schemas.search import SearchHit, SearchRequest, SearchResponse
from services.embeddings import EmbeddingService
from services.qdrant_service import QdrantService
from services.reranker import RerankerService
from services.sparse_embeddings import SparseEmbeddingService


router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    sparse_embedding_service: SparseEmbeddingService = Depends(get_sparse_embedding_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
    reranker_service: RerankerService = Depends(get_reranker_service),
):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    if request.search_mode == "vector":
        dense_query_vector = embedding_service.encode_query(query)
        found = qdrant_service.search_dense(
            query_vector=dense_query_vector,
            limit=request.candidate_k,
            doc_id=request.doc_id,
        )

    elif request.search_mode == "bm25":
        sparse_query_vector = sparse_embedding_service.encode_query(query)

        found = qdrant_service.search_sparse(
            query_vector=sparse_query_vector,
            limit=request.candidate_k,
            doc_id=request.doc_id,
        )

    elif request.search_mode == "hybrid":
        dense_query_vector = embedding_service.encode_query(query)
        sparse_query_vector = sparse_embedding_service.encode_query(query)
        found = qdrant_service.search_hybrid(
            dense_query_vector=dense_query_vector,
            sparse_query_vector=sparse_query_vector,
            limit=request.candidate_k,
            doc_id=request.doc_id,
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported search_mode={request.search_mode}",
        )

    if not found:
        return SearchResponse(query=query, search_mode=request.search_mode, hits=[])

    passages = [point.payload["text"] for point in found]
    rerank_scores = reranker_service.rerank(query, passages)

    hits = []
    for point, rerank_score in zip(found, rerank_scores):
        payload = point.payload
        hits.append(
            SearchHit(
                chunk_id=str(payload["chunk_id"]),
                doc_id=str(payload["doc_id"]),
                text=payload["text"],
                metadata=payload.get("metadata", {}),
                retrieval_mode=request.search_mode,
                retrieval_score=float(point.score),
                rerank_score=float(rerank_score),
            )
        )

    hits.sort(key=lambda x: x.rerank_score, reverse=True)

    return SearchResponse(
        query=query,
        search_mode=request.search_mode,
        hits=hits[: request.top_k],
    )