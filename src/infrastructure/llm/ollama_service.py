"""Ollama LLM service implementation (stub)."""

from __future__ import annotations

from src.domain.entities.message import Message
from src.domain.interfaces.llm_service import LLMService, LLMServiceError


class OllamaService(LLMService):
    """Stub implementation of Ollama LLM service.

    Returns a predictable echo response for testing purposes.
    In production, this will be replaced with real HTTP client to Ollama API.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
    ) -> None:
        """Initialize Ollama service.

        Args:
            base_url: Ollama server base URL. Defaults to local instance.
            default_model: Default model name for generation.
        """
        self._base_url = base_url
        self._default_model = default_model

    @property
    def base_url(self) -> str:
        """Get Ollama server base URL."""
        return self._base_url

    @property
    def default_model(self) -> str:
        """Get default model name."""
        return self._default_model

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        model_params: dict | None = None,
    ) -> str:
        """Generate a response from the LLM (stub implementation).

        Args:
            prompt: User prompt text.
            context: List of previous messages for context.
            model_params: Optional model parameters (temperature, max_tokens, etc.).

        Returns:
            Predictable echo response: "Echo: {prompt}".

        Raises:
            LLMServiceError: If prompt is empty or None.
        """
        if prompt is None or not prompt.strip():
            raise LLMServiceError("Prompt cannot be empty or None")

        return f"Echo: {prompt}"
