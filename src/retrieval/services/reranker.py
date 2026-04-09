#from sentence_transformers import CrossEncoder

from core.config import settings
from services.openrouter_client import OpenRouterClient


class RerankerService:
    def __init__(self):
        self.provider = settings.MODEL_PROVIDER

        if self.provider == "local":
            #self.model = CrossEncoder(settings.RERANK_MODEL_NAME)
            self.client = None
        elif self.provider == "openrouter":
            self.model = None
            self.client = OpenRouterClient()
        else:
            raise ValueError(
                f"Unsupported MODEL_PROVIDER={settings.MODEL_PROVIDER}. "
                f"Expected 'local' or 'openrouter'."
            )

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []

        if self.provider == "local":
            pairs = [(query, passage) for passage in passages]
            scores = self.model.predict(pairs)
            return [float(score) for score in scores]

        data = self.client.post(
            "/rerank",
            {
                "model": settings.OPENROUTER_RERANK_MODEL,
                "query": query,
                "documents": passages,
            },
        )

        # OpenRouter rerank returns results with index + score/relevance_score
        results = data.get("results", [])
        score_by_index: dict[int, float] = {}

        for item in results:
            idx = item["index"]
            score = item.get("score", item.get("relevance_score", 0.0))
            score_by_index[idx] = float(score)

        return [score_by_index.get(i, 0.0) for i in range(len(passages))]