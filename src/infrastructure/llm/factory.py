"""LLM service factory for creating LLM service instances."""

import logging

from src.domain.interfaces.llm_service import LLMService, LLMServiceError
from src.infrastructure.config import Settings
from src.infrastructure.llm.genapi_service import GenAPIService
from src.infrastructure.llm.ollama_service import OllamaService

logger = logging.getLogger(__name__)


class LLMServiceFactory:
    """Factory for creating LLM service instances based on configuration.

    Supports multiple LLM providers:
    - Ollama (local models)
    - GenAPI (cloud models via gen-api.ru)

    Example:
        >>> settings = get_settings()
        >>> factory = LLMServiceFactory(settings)
        >>> service = factory.create_service()
        >>> response = await service.generate(prompt="Hello", context=[])
    """

    def __init__(self, settings: Settings) -> None:
        """Initialize factory with settings.

        Args:
            settings: Application settings instance.
        """
        self._settings = settings

    def create_service(self) -> LLMService:
        """Create LLM service based on configured provider.

        Returns:
            Configured LLM service instance.

        Raises:
            LLMServiceError: If provider is not configured or unsupported.
        """
        provider = self._settings.llm_provider.lower()
        logger.info("Creating LLM service for provider: %s", provider)

        if provider == "ollama":
            return self._create_ollama_service()

        if provider == "genapi":
            return self._create_genapi_service()

        raise LLMServiceError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: ollama, genapi"
        )

    def _create_ollama_service(self) -> OllamaService:
        """Create Ollama service instance.

        Returns:
            Configured OllamaService instance.
        """
        service = OllamaService(
            base_url=self._settings.ollama_base_url,
            default_model=self._settings.ollama_model,
            timeout=self._settings.ollama_timeout,
            max_retries=self._settings.ollama_max_retries,
        )
        logger.info(
            "Ollama service created: base_url=%s, model=%s",
            service.base_url,
            service.default_model,
        )
        return service

    def _create_genapi_service(self) -> GenAPIService:
        """Create GenAPI service instance.

        Returns:
            Configured GenAPIService instance.

        Raises:
            LLMServiceError: If GenAPI is not configured.
        """
        if not self._settings.is_genapi_configured():
            raise LLMServiceError(
                "GenAPI provider selected but GENAPI_KEY is not configured. "
                "Set GENAPI_KEY in .env or switch to another provider."
            )

        service = GenAPIService(
            api_key=self._settings.genapi_key,
            base_url=self._settings.genapi_base_url,
            default_model=self._settings.genapi_model,
            timeout=self._settings.genapi_timeout,
            poll_timeout=self._settings.genapi_poll_timeout,
            max_retries=self._settings.genapi_max_retries,
        )
        logger.info(
            "GenAPI service created: base_url=%s, model=%s",
            service.base_url,
            service.default_model,
        )
        return service

    def create_service_for_provider(self, provider: str) -> LLMService:
        """Create LLM service for a specific provider.

        Args:
            provider: Provider name (ollama or genapi).

        Returns:
            Configured LLM service instance.

        Raises:
            LLMServiceError: If provider is unsupported or not configured.
        """
        provider = provider.lower()

        if provider == "ollama":
            return self._create_ollama_service()

        if provider == "genapi":
            return self._create_genapi_service()

        raise LLMServiceError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: ollama, genapi"
        )
