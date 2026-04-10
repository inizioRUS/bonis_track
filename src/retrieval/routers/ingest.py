import uuid

from fastapi import APIRouter, Depends, HTTPException
from qdrant_client.models import PointStruct

from core.config import settings
from core.dependencies import (
    get_embedding_service,
    get_qdrant_service,
    get_sparse_embedding_service,
)
from schemas.ingest import IngestRequest, IngestResponse
from services.chunker import ChunkerService
from services.embeddings import EmbeddingService
from services.parser import ArticleParserService
from services.qdrant_service import QdrantService
from services.sparse_embeddings import SparseEmbeddingService
from utils.text import make_chunk_id


router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    request: IngestRequest,
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    sparse_embedding_service: SparseEmbeddingService = Depends(get_sparse_embedding_service),
    qdrant_service: QdrantService = Depends(get_qdrant_service),
):
    parser = ArticleParserService()
    chunker = ChunkerService()

    try:
        parsed = parser.parse_url(str(request.url))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parsing failed: {e}")

    doc_id = request.doc_id or str(uuid.uuid4())

    base_metadata = {
        **parsed.metadata,
        **request.metadata,
        "title": parsed.title,
    }

    chunks = chunker.chunk_text(parsed.text)
    if not chunks:
        raise HTTPException(status_code=400, detail="No chunks produced")

    dense_vectors = embedding_service.encode_passages(chunks)
    sparse_vectors = sparse_embedding_service.encode_passages(chunks)

    if len(dense_vectors) != len(chunks):
        raise HTTPException(status_code=500, detail="Dense embedding count mismatch")

    if len(sparse_vectors) != len(chunks):
        raise HTTPException(status_code=500, detail="Sparse embedding count mismatch")

    points: list[PointStruct] = []

    for idx, (chunk, dense_vector, sparse_vector) in enumerate(
        zip(chunks, dense_vectors, sparse_vectors)
    ):
        chunk_id = make_chunk_id(doc_id, idx, chunk)
        window = chunker.build_chunk_window(chunks, idx, radius=2)

        payload = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "text": chunk,
            "chunk_index": idx,
            "metadata": {
                **base_metadata,
                "window": window,
            },
        }
        points.append(
            PointStruct(
                id=chunk_id,
                vector={
                    settings.DENSE_VECTOR_NAME: dense_vector,
                    settings.SPARSE_VECTOR_NAME: sparse_vector,
                },
                payload=payload,
            )
        )

    qdrant_service.upsert_points(points)

    return IngestResponse(
        status="ok",
        doc_id=doc_id,
        title=parsed.title,
        source_url=str(request.url),
        chunks_count=len(points),
        metadata=base_metadata,
    )