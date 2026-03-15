"""LLM service port."""

from abc import ABC, abstractmethod

from ..entities.message import Message


class LLMService(ABC):
    """Abstract base class for LLM service."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: list[Message],
        model_params: dict | None = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: User prompt text.
            context: List of previous messages for context.
            model_params: Optional model parameters (temperature, max_tokens, etc.).

        Returns:
            Generated response text.

        Raises:
            LLMServiceError: If generation fails.
        """
        raise NotImplementedError


class LLMServiceError(Exception):
    """Exception raised for LLM service errors."""

    pass
