"""Tests for LLMServiceFactory."""

from unittest.mock import patch

import pytest

from src.domain.interfaces.llm_service import LLMServiceError
from src.infrastructure.config import Settings
from src.infrastructure.llm.factory import LLMServiceFactory
from src.infrastructure.llm.genapi_service import GenAPIService
from src.infrastructure.llm.ollama_service import OllamaService


@pytest.fixture
def ollama_settings() -> Settings:
    """Create settings for Ollama provider."""
    return Settings(
        app_name="TestApp",
        database_type="sqlite",
        database_url="sqlite+aiosqlite:///./data/test.db",
        llm_provider="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3",
        ollama_timeout=60.0,
        ollama_max_retries=3,
    )


@pytest.fixture
def genapi_settings() -> Settings:
    """Create settings for GenAPI provider."""
    return Settings(
        app_name="TestApp",
        database_type="sqlite",
        database_url="sqlite+aiosqlite:///./data/test.db",
        llm_provider="genapi",
        genapi_key="test_key_12345678901234567890",
        genapi_base_url="https://api.gen-api.ru/api/v1",
        genapi_model="gpt-4o-mini",
        genapi_timeout=60.0,
        genapi_poll_timeout=120.0,
        genapi_max_retries=3,
    )


@pytest.fixture
def genapi_not_configured_settings() -> Settings:
    """Create settings with GenAPI provider but no key."""
    return Settings(
        app_name="TestApp",
        database_type="sqlite",
        database_url="sqlite+aiosqlite:///./data/test.db",
        llm_provider="genapi",
        genapi_key=None,
    )


@pytest.fixture
def invalid_provider_settings() -> Settings:
    """Create settings with invalid provider (bypassing validation)."""
    # We can't create Settings with invalid provider due to validation
    # So we test the factory method directly with a mock settings
    from unittest.mock import MagicMock
    mock_settings = MagicMock()
    mock_settings.llm_provider = "invalid_provider"
    return mock_settings


class TestLLMServiceFactory:
    """Tests for LLMServiceFactory."""

    def test_create_ollama_service(self, ollama_settings: Settings) -> None:
        """Test creating Ollama service."""
        factory = LLMServiceFactory(ollama_settings)
        service = factory.create_service()

        assert isinstance(service, OllamaService)
        assert service.base_url == "http://localhost:11434"
        assert service.default_model == "llama3"

    def test_create_genapi_service(self, genapi_settings: Settings) -> None:
        """Test creating GenAPI service."""
        factory = LLMServiceFactory(genapi_settings)
        service = factory.create_service()

        assert isinstance(service, GenAPIService)
        assert service.base_url == "https://api.gen-api.ru/api/v1"
        assert service.default_model == "gpt-4o-mini"

    def test_create_genapi_service_not_configured(
        self,
        genapi_not_configured_settings: Settings,
    ) -> None:
        """Test error when GenAPI is selected but not configured."""
        factory = LLMServiceFactory(genapi_not_configured_settings)

        with pytest.raises(LLMServiceError, match="GENAPI_KEY is not configured"):
            factory.create_service()

    def test_create_service_invalid_provider(
        self,
        invalid_provider_settings: Settings,
    ) -> None:
        """Test error when invalid provider is specified."""
        factory = LLMServiceFactory(invalid_provider_settings)

        with pytest.raises(LLMServiceError, match="Unsupported LLM provider"):
            factory.create_service()

    def test_create_service_for_provider_ollama(
        self,
        ollama_settings: Settings,
    ) -> None:
        """Test creating service for specific provider (Ollama)."""
        factory = LLMServiceFactory(ollama_settings)
        service = factory.create_service_for_provider("ollama")

        assert isinstance(service, OllamaService)

    def test_create_service_for_provider_genapi(
        self,
        genapi_settings: Settings,
    ) -> None:
        """Test creating service for specific provider (GenAPI)."""
        factory = LLMServiceFactory(genapi_settings)
        service = factory.create_service_for_provider("genapi")

        assert isinstance(service, GenAPIService)

    def test_create_service_for_provider_invalid(
        self,
        ollama_settings: Settings,
    ) -> None:
        """Test error when creating service for invalid provider."""
        factory = LLMServiceFactory(ollama_settings)

        with pytest.raises(LLMServiceError, match="Unsupported LLM provider"):
            factory.create_service_for_provider("invalid")

    def test_create_service_case_insensitive(
        self,
        ollama_settings: Settings,
    ) -> None:
        """Test that provider name is case insensitive."""
        # Manually set provider with different case
        ollama_settings.llm_provider = "OLLAMA"
        factory = LLMServiceFactory(ollama_settings)
        service = factory.create_service()

        assert isinstance(service, OllamaService)

    def test_factory_initialization(self, ollama_settings: Settings) -> None:
        """Test factory initialization."""
        factory = LLMServiceFactory(ollama_settings)

        assert factory._settings == ollama_settings
