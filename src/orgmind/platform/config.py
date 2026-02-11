"""
OrgMind Configuration Management

Uses Pydantic Settings for type-safe configuration from environment variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # =========================================================================
    # APPLICATION
    # =========================================================================
    APP_NAME: str = "OrgMind"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    VERSION: str = "0.1.0"

    # =========================================================================
    # API SERVER
    # =========================================================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    CORS_ORIGINS: str = "http://localhost:3000"

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # =========================================================================
    # DUCKDB (Source of Truth)
    # =========================================================================
    DUCKDB_PATH: str = "data/orgmind.duckdb"
    DUCKDB_THREADS: int = 4

    # =========================================================================
    # REDIS (Event Bus - Legacy)
    # =========================================================================
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_MAX_CONNECTIONS: int = 10

    # =========================================================================
    # NATS (Event Bus - Primary)
    # =========================================================================
    NATS_URL: str = "nats://localhost:4222"
    NATS_MAX_RECONNECT_ATTEMPTS: int = 60

    # =========================================================================
    # NEO4J (Graph Index)
    # =========================================================================
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "orgmind_dev"
    NEO4J_DATABASE: str = "neo4j"

    # =========================================================================
    # QDRANT (Vector Search)
    # =========================================================================
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334

    # =========================================================================
    # MEILISEARCH (Full-Text Search)
    # =========================================================================
    MEILISEARCH_HOST: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = "orgmind_dev_key"

    # =========================================================================
    # MINIO (Object Storage)
    # =========================================================================
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "orgmind_admin"
    MINIO_SECRET_KEY: str = "orgmind_secret"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "orgmind-files"

    # =========================================================================
    # TEMPORAL (Workflow Engine)
    # =========================================================================
    TEMPORAL_HOST: str = "localhost:7233"
    TEMPORAL_NAMESPACE: str = "default"
    TEMPORAL_TASK_QUEUE: str = "orgmind-workflows"

    # =========================================================================
    # OPENAI (LLM / Embeddings)
    # =========================================================================
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # =========================================================================
    # OBSERVABILITY
    # =========================================================================
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "orgmind"
    METRICS_ENABLED: bool = True

    # =========================================================================
    # FEATURE FLAGS
    # =========================================================================
    FEATURE_AGENT_ENABLED: bool = True
    FEATURE_WORKFLOW_ENABLED: bool = True
    FEATURE_DECISION_TRACE_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton instance for easy import
settings = get_settings()
