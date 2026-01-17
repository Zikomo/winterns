"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    database_url: str = "postgresql+asyncpg://wintern:wintern@localhost:5432/wintern"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30

    # Google OAuth
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    # OpenRouter
    openrouter_api_key: str = ""
    default_model: str = "anthropic/claude-sonnet-4-20250514"

    # Data Sources
    brave_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "wintern/0.1.0"

    # Delivery
    slack_default_webhook_url: str = ""

    # AWS (for SES)
    aws_region: str = "us-east-1"
    ses_from_address: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
