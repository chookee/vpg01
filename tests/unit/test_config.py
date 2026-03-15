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
