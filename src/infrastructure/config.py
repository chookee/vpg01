"""Application configuration management."""

from typing import Final
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # General
    app_name: str = Field(default="VPg01", min_length=1, max_length=50)
    debug: bool = False

    # Database
    database_url: str = Field(
        ...,
        min_length=1,
        description="Database connection URL (sqlite+aiosqlite:// or postgresql+asyncpg://)",
    )

    # LLM
    llm_provider: str = Field(default="ollama", min_length=1)
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3", min_length=1)

    # Telegram (optional, validated separately)
    telegram_bot_token: str | None = Field(default=None)

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_bot_token(cls, value: str | None) -> str | None:
        """Validate Telegram bot token format."""
        if value is None or value == "":
            return None
        if value == "your_bot_token_here":
            return None
        if len(value) < 40:
            raise ValueError("Invalid Telegram bot token length")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Validate database URL format."""
        if not value:
            raise ValueError("DATABASE_URL cannot be empty")

        allowed_schemes = {"sqlite+aiosqlite", "postgresql+asyncpg", "sqlite"}

        try:
            parsed = urlparse(value)
            if parsed.scheme not in allowed_schemes:
                raise ValueError(
                    f"Unsupported database scheme: {parsed.scheme}. "
                    f"Allowed: {', '.join(allowed_schemes)}"
                )
            if not parsed.path:
                raise ValueError("DATABASE_URL must include database path")
        except Exception as e:
            raise ValueError(f"Invalid DATABASE_URL format: {e}") from e

        return value

    def is_bot_configured(self) -> bool:
        """Check if Telegram bot is configured."""
        return self.telegram_bot_token is not None


def get_settings() -> Settings:
    """Get application settings instance.

    Returns:
        Settings instance.
    """
    return Settings()
