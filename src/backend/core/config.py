import os
from dataclasses import dataclass


@dataclass
class Settings:
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))

    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql+asyncpg://postgres:postgres@postgres:5432/poc_db",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

    retriever_url: str = os.getenv("RETRIEVER_URL", "http://poc-retriever:8010")
    asana_url: str = os.getenv("ASANA_URL", "https://app.asana.com/api/1.0")

    request_timeout_sec: float = float(os.getenv("REQUEST_TIMEOUT_SEC", "30"))
    retriever_top_k: int = int(os.getenv("RETRIEVER_TOP_K", "3"))
    retriever_candidate_k: int = int(os.getenv("RETRIEVER_CANDIDATE_K", "10"))
    redis_session_ttl_sec: int = int(os.getenv("REDIS_SESSION_TTL_SEC", "86400"))

    default_asana_project_id: str = os.getenv("DEFAULT_ASANA_PROJECT_ID", "")
    default_asana_workspace_id: str = os.getenv("DEFAULT_ASANA_WORKSPACE_ID", "1213951473262664")
    default_asana_team_id: str = os.getenv("DEFAULT_ASANA_TEAM_ID", "")
    default_asana_assignee_gid: str = os.getenv("DEFAULT_ASANA_ASSIGNEE_GID", "")
    asana_pat: str = os.getenv("ASANA_PAT", "")

    max_cycle_steps: int = int(os.getenv("MAX_CYCLE_STEPS", "16"))
    verifier_min_sources: int = int(os.getenv("VERIFIER_MIN_SOURCES", "2"))
    analyst_enable_habr_url_detection: bool = os.getenv(
        "ANALYST_ENABLE_HABR_URL_DETECTION",
        "true",
    ).lower() == "true"

    # OpenRouter
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
    openrouter_model: str = os.getenv(
        "OPENROUTER_MODEL",
        "openai/gpt-4.1-mini",
    )
    openrouter_http_referer: str = os.getenv("OPENROUTER_HTTP_REFERER", "")
    openrouter_x_title: str = os.getenv("OPENROUTER_X_TITLE", "bonis-track")
    openrouter_temperature: float = float(os.getenv("OPENROUTER_TEMPERATURE", "0.2"))
    openrouter_max_tokens: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "1200"))


settings = Settings()