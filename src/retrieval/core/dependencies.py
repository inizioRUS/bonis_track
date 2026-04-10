from contextlib import asynccontextmanager

from core.config import settings
from services.embeddings import EmbeddingService
from services.qdrant_service import QdrantService
from services.reranker import RerankerService
from services.sparse_embeddings import SparseEmbeddingService


embedding_service: EmbeddingService | None = None
sparse_embedding_service: SparseEmbeddingService | None = None
reranker_service: RerankerService | None = None
qdrant_service: QdrantService | None = None


@asynccontextmanager
async def lifespan(app):
    global embedding_service, sparse_embedding_service, reranker_service, qdrant_service

    if settings.MODEL_PROVIDER not in {"local", "openrouter"}:
        raise ValueError(
            f"Unsupported MODEL_PROVIDER={settings.MODEL_PROVIDER}. "
            "Use 'local' or 'openrouter'."
        )

    embedding_service = EmbeddingService()
    sparse_embedding_service = SparseEmbeddingService()
    reranker_service = RerankerService()
    qdrant_service = QdrantService()

    qdrant_service.ensure_collection()

    yield


def get_embedding_service() -> EmbeddingService:
    assert embedding_service is not None
    return embedding_service


def get_sparse_embedding_service() -> SparseEmbeddingService:
    assert sparse_embedding_service is not None
    return sparse_embedding_service


def get_reranker_service() -> RerankerService:
    assert reranker_service is not None
    return reranker_service


def get_qdrant_service() -> QdrantService:
    assert qdrant_service is not None
    return qdrant_service