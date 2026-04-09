#from sentence_transformers import SentenceTransformer

from core.config import settings
from services.openrouter_client import OpenRouterClient
from utils.text import normalize_text


class EmbeddingService:
    def __init__(self):
        self.provider = settings.MODEL_PROVIDER

        if self.provider == "local":
            #self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
            self.client = None
        elif self.provider == "openrouter":
            self.model = None
            self.client = OpenRouterClient()
        else:
            raise ValueError(
                f"Unsupported MODEL_PROVIDER={settings.MODEL_PROVIDER}. "
                f"Expected 'local' or 'openrouter'."
            )

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        texts = [normalize_text(text) for text in texts if normalize_text(text)]
        if not texts:
            return []

        if self.provider == "local":
            vectors = self.model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return vectors.tolist()

        data = self.client.post(
            "/embeddings",
            {
                "model": settings.OPENROUTER_EMBEDDING_MODEL,
                "input": texts,
            },
        )

        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]

    def encode_query(self, query: str) -> list[float]:
        query = normalize_text(query)

        if self.provider == "local":
            formatted_query = (
                "Instruct: Given a search query, retrieve relevant passages that answer the query\n"
                f"Query: {query}"
            )
            vector = self.model.encode(
                [formatted_query],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )[0]
            return vector.tolist()

        data = self.client.post(
            "/embeddings",
            {
                "model": settings.OPENROUTER_EMBEDDING_MODEL,
                "input": query,
            },
        )

        return data["data"][0]["embedding"]