import os


class Settings:
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "documents")

    MODEL_PROVIDER: str = os.getenv("MODEL_PROVIDER", "local").lower()

    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "intfloat/multilingual-e5-large-instruct",
    )
    RERANK_MODEL_NAME: str = os.getenv(
        "RERANK_MODEL_NAME",
        "BAAI/bge-reranker-v2-m3",
    )

    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
    OPENROUTER_EMBEDDING_MODEL: str = os.getenv(
        "OPENROUTER_EMBEDDING_MODEL",
        "intfloat/multilingual-e5-large",
    )
    OPENROUTER_RERANK_MODEL: str = os.getenv(
        "OPENROUTER_RERANK_MODEL",
        "cohere/rerank-v3.5",
    )
    OPENROUTER_HTTP_REFERER: str = os.getenv(
        "OPENROUTER_HTTP_REFERER",
        "https://openrouter.ai/api/v1",
    )
    OPENROUTER_X_TITLE: str = os.getenv(
        "OPENROUTER_X_TITLE",
        "Retriever Service",
    )

    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "1024"))

    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))

    SEARCH_CANDIDATES: int = int(os.getenv("SEARCH_CANDIDATES", "30"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "20"))


settings = Settings()