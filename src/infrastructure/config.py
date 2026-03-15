"""Application configuration management."""

import warnings
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
    telegram_bot_token: str | None = Field(
        default=None,
        description="Telegram bot token (optional, set to enable bot)",
    )

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_bot_token(cls, value: str | None) -> str | None:
        """Validate Telegram bot token format.

        Args:
            value: Token value from environment.

        Returns:
            Validated token or None if not configured.

        Raises:
            ValueError: If token format is invalid.
        """
        if value is None or value == "":
            return None

        if value == "your_bot_token_here":
            # Emit warning but don't fail - allows app to start without bot
            warnings.warn(
                "TELEGRAM_BOT_TOKEN is set to placeholder value. "
                "Update .env with real token or leave empty to disable bot.",
                UserWarning,
                stacklevel=2,
            )
            return None

        # Telegram bot tokens are typically 45-50 characters
        if len(value) < 40:
            raise ValueError(
                f"Invalid Telegram bot token length: {len(value)} chars (expected >= 40). "
                "Check TELEGRAM_BOT_TOKEN in .env"
            )

        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Validate database URL format.

        Args:
            value: Database URL from environment.

        Returns:
            Validated database URL.

        Raises:
            ValueError: If database URL format is invalid or path traversal detected.
        """
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

            # Security: Prevent path traversal attacks
            if ".." in parsed.path:
                raise ValueError(
                    "DATABASE_URL must not contain '..' (path traversal not allowed). "
                    "Use absolute paths or paths within the application directory."
                )

        except Exception as e:
            raise ValueError(f"Invalid DATABASE_URL format: {e}") from e

        return value

    def is_bot_configured(self) -> bool:
        """Check if Telegram bot is configured.

        Returns:
            True if bot token is configured, False otherwise.
        """
        return self.telegram_bot_token is not None


def get_settings() -> Settings:
    """Get application settings instance.

    Returns:
        Settings instance.
    """
    return Settings()
