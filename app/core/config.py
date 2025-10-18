"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Event Analytics Service"
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/events_db"
    db_pool_size: int = 20
    db_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_idempotency_ttl: int = 86400  # 24 hours in seconds
    
    # NATS
    nats_url: str = "nats://localhost:4222"
    nats_stream_name: str = "EVENTS"
    nats_subject: str = "events.ingest"
    nats_consumer_name: str = "event-processor"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 1000
    rate_limit_window: int = 60  # seconds

    # Cold Storage (optional)
    cold_storage_enabled: bool = False
    cold_storage_days_threshold: int = 30
    cold_storage_path: str = "/app/data/cold_storage"

    # API Keys (optional)
    api_key: str | None = None

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()

