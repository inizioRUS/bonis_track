from fastembed import SparseTextEmbedding
from qdrant_client import models

from core.config import settings
from utils.text import normalize_text


class SparseEmbeddingService:
    def __init__(self):
        self.model = SparseTextEmbedding(model_name=settings.FASTEMBED_BM25_MODEL)

    def encode_passages(self, texts: list[str]) -> list[models.SparseVector]:
        normalized = [normalize_text(text) for text in texts]
        normalized = [text for text in normalized if text]
        if not normalized:
            return []

        embeddings = list(self.model.embed(normalized))
        return [
            models.SparseVector(
                indices=embedding.indices.tolist(),
                values=embedding.values.tolist(),
            )
            for embedding in embeddings
        ]

    def encode_query(self, query: str) -> models.SparseVector:
        query = normalize_text(query)
        embedding = next(self.model.query_embed(query))
        return models.SparseVector(
            indices=embedding.indices.tolist(),
            values=embedding.values.tolist(),
        )