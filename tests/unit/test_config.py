"""Tests for configuration validation."""

import os
import pytest

from src.infrastructure.config import Settings


class TestDatabaseUrlValidation:
    """Tests for DATABASE_URL validation."""

    def test_valid_sqlite_url(self) -> None:
        """Test valid SQLite URL is accepted."""
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/app.db"
        settings = Settings()
        assert "sqlite" in settings.database_url

    def test_path_traversal_rejected(self) -> None:
        """Test that path traversal (..) is rejected."""
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///../../../etc/passwd"

        with pytest.raises(ValueError, match="path traversal"):
            Settings()

    def test_empty_url_rejected(self) -> None:
        """Test that empty DATABASE_URL is rejected."""
        os.environ["DATABASE_URL"] = ""

        # Pydantic validates min_length before our custom validator
        with pytest.raises(Exception):  # Either ValueError or ValidationError
            Settings()

    def test_invalid_scheme_rejected(self) -> None:
        """Test that unsupported database scheme is rejected."""
        os.environ["DATABASE_URL"] = "mysql://localhost/db"

        with pytest.raises(ValueError, match="Unsupported database scheme"):
            Settings()

    def test_no_path_rejected(self) -> None:
        """Test that URL without path is rejected."""
        os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

        with pytest.raises(ValueError, match="must include database path"):
            Settings()

    def test_postgresql_url_accepted(self) -> None:
        """Test valid PostgreSQL URL is accepted."""
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/db"
        settings = Settings()
        assert "postgresql" in settings.database_url


class TestTelegramBotTokenValidation:
    """Tests for TELEGRAM_BOT_TOKEN validation."""

    def test_placeholder_token_returns_none(self, monkeypatch) -> None:
        """Test that placeholder token returns None with warning."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "your_bot_token_here")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

        settings = Settings()
        assert settings.telegram_bot_token is None

    def test_short_token_rejected(self, monkeypatch) -> None:
        """Test that short token is rejected."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "short")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

        with pytest.raises(ValueError, match="length"):
            Settings()

    def test_none_token_accepted(self, monkeypatch) -> None:
        """Test that None/missing token is accepted."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

        settings = Settings()
        assert settings.telegram_bot_token is None


class TestLLMProviderValidation:
    """Tests for LLM_PROVIDER validation."""

    def test_ollama_provider_accepted(self, monkeypatch) -> None:
        """Test that 'ollama' provider is accepted."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        settings = Settings()
        assert settings.llm_provider == "ollama"

    def test_genapi_provider_accepted(self, monkeypatch) -> None:
        """Test that 'genapi' provider is accepted."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("LLM_PROVIDER", "genapi")

        settings = Settings()
        assert settings.llm_provider == "genapi"

    def test_invalid_provider_rejected(self, monkeypatch) -> None:
        """Test that invalid provider is rejected."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")

        with pytest.raises(ValueError, match="Invalid LLM_PROVIDER"):
            Settings()

    def test_provider_case_insensitive(self, monkeypatch) -> None:
        """Test that provider name is case insensitive."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("LLM_PROVIDER", "OLLAMA")

        settings = Settings()
        assert settings.llm_provider == "ollama"


class TestGenAPIKeyValidation:
    """Tests for GENAPI_KEY validation."""

    def test_placeholder_key_returns_none(self, monkeypatch) -> None:
        """Test that placeholder key returns None with warning."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("GENAPI_KEY", "your_genapi_key_here")

        settings = Settings()
        assert settings.genapi_key is None

    def test_short_key_rejected(self, monkeypatch) -> None:
        """Test that short key is rejected."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("GENAPI_KEY", "short")

        with pytest.raises(ValueError, match="length"):
            Settings()

    def test_none_key_accepted(self, monkeypatch) -> None:
        """Test that None/missing key is accepted."""
        monkeypatch.delenv("GENAPI_KEY", raising=False)
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

        settings = Settings()
        assert settings.genapi_key is None

    def test_valid_key_accepted(self, monkeypatch) -> None:
        """Test that valid key is accepted."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("GENAPI_KEY", "valid_key_12345678901234567890")

        settings = Settings()
        assert settings.genapi_key == "valid_key_12345678901234567890"

    def test_is_genapi_configured(self, monkeypatch) -> None:
        """Test is_genapi_configured method."""
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        
        # Test with key
        monkeypatch.setenv("GENAPI_KEY", "valid_key_12345678901234567890")
        settings = Settings()
        assert settings.is_genapi_configured() is True

        # Test without key
        monkeypatch.delenv("GENAPI_KEY", raising=False)
        settings = Settings()
        assert settings.is_genapi_configured() is False
