from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams

from core.config import settings


class QdrantService:
    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        self.collection_name = settings.QDRANT_COLLECTION
        self.dense_vector_name = settings.DENSE_VECTOR_NAME
        self.sparse_vector_name = settings.SPARSE_VECTOR_NAME

    def ensure_collection(self):
        collections = self.client.get_collections().collections
        names = {c.name for c in collections}

        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    self.dense_vector_name: VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    self.sparse_vector_name: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )

    def upsert_points(self, points: list[PointStruct]):
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def _make_filter(self, doc_id: str | None):
        if not doc_id:
            return None

        return models.Filter(
            must=[
                models.FieldCondition(
                    key="doc_id",
                    match=models.MatchValue(value=doc_id),
                )
            ]
        )

    def search_dense(
        self,
        query_vector: list[float],
        limit: int,
        doc_id: str | None = None,
    ):
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=self.dense_vector_name,
            query_filter=self._make_filter(doc_id),
            limit=limit,
            with_payload=True,
        )
        return result.points

    def search_sparse(
        self,
        query_vector: models.SparseVector,
        limit: int,
        doc_id: str | None = None,
    ):
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            using=self.sparse_vector_name,
            query_filter=self._make_filter(doc_id),
            limit=limit,
            with_payload=True,
        )
        return result.points

    def search_hybrid(
        self,
        dense_query_vector: list[float],
        sparse_query_vector: models.SparseVector,
        limit: int,
        doc_id: str | None = None,
    ):
        result = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query_vector,
                    using=self.dense_vector_name,
                    limit=limit,
                ),
                models.Prefetch(
                    query=sparse_query_vector,
                    using=self.sparse_vector_name,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.DBSF),
            query_filter=self._make_filter(doc_id),
            limit=limit,
            with_payload=True,
        )
        return result.points