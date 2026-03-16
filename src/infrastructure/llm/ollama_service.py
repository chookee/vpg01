"""Ollama LLM service implementation with retry logic."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.domain.entities.message import Message
from src.domain.interfaces.llm_service import LLMService, LLMServiceError

logger = logging.getLogger(__name__)


class OllamaService(LLMService):
    """Ollama LLM service with HTTP client and retry logic.

    Provides async communication with Ollama API for text generation.
    Includes automatic retry on transient failures and timeout handling.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama3",
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize Ollama service.

        Args:
            base_url: Ollama server base URL. Defaults to local instance.
            default_model: Default model name for generation.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        self._max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None

    @property
    def base_url(self) -> str:
        """Get Ollama server base URL."""
        return self._base_url

    @property
    def default_model(self) -> str:
        """Get default model name."""
        return self._default_model

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    def _messages_to_ollama_format(
        self,
        prompt: str,
        context: list[Message],
    ) -> list[dict[str, str]]:
        """Convert messages to Ollama chat format.

        Args:
            prompt: Current user prompt.
            context: List of previous messages.

        Returns:
            List of message dicts in Ollama format.
        """
        messages: list[dict[str, str]] = []

        # Add context messages
        for msg in context:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add current prompt as user message
        messages.append({
            "role": "user",
            "content": prompt,
        })

        return messages

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_with_retry(
        self,
        messages: list[dict[str, str]],
        model: str,
        model_params: dict | None = None,
    ) -> str:
        """Generate response with retry logic.

        Args:
            messages: Formatted chat messages.
            model: Model name to use.
            model_params: Optional model parameters.

        Returns:
            Generated response text.

        Raises:
            LLMServiceError: If generation fails after retries.
        """
        url = f"{self._base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        # Add optional parameters
        if model_params:
            if "temperature" in model_params:
                payload["options"] = {"temperature": model_params["temperature"]}
            if "max_tokens" in model_params:
                payload["options"] = payload.get("options", {})
                payload["options"]["num_predict"] = model_params["max_tokens"]

        session = await self._get_session()

        try:
            async with session.post(url, json=payload) as response:
                if response.status == 429:
                    raise LLMServiceError("Ollama rate limit exceeded")

                if response.status != 200:
                    error_text = await response.text()
                    raise LLMServiceError(
                        f"Ollama API error: {response.status} - {error_text}"
                    )

                data = await response.json()

                # Extract response from Ollama format
                if "message" not in data:
                    raise LLMServiceError("Invalid response from Ollama: missing 'message'")

                content = data["message"].get("content", "")
                if not content:
                    raise LLMServiceError("Empty response from Ollama")

                return content

        except aiohttp.ClientConnectionError as e:
            raise LLMServiceError(f"Cannot connect to Ollama: {e}") from e
        except asyncio.TimeoutError as e:
            raise LLMServiceError(f"Ollama request timeout: {e}") from e
        except LLMServiceError:
            raise
        except Exception as e:
            raise LLMServiceError(f"Unexpected Ollama error: {e}") from e

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        model_params: dict | None = None,
    ) -> str:
        """Generate a response from Ollama LLM.

        Args:
            prompt: User prompt text.
            context: List of previous messages for context.
            model_params: Optional model parameters (temperature, max_tokens, etc.).

        Returns:
            Generated response text.

        Raises:
            LLMServiceError: If generation fails.
        """
        if prompt is None or not prompt.strip():
            raise LLMServiceError("Prompt cannot be empty or None")

        messages = self._messages_to_ollama_format(prompt, context)
        model = model_params.get("model", self._default_model) if model_params else self._default_model

        logger.debug(
            "Generating with Ollama: model=%s, context_size=%d",
            model,
            len(context),
        )

        try:
            return await self._generate_with_retry(messages, model, model_params)
        except LLMServiceError:
            raise
        except Exception as e:
            raise LLMServiceError(f"Ollama generation failed: {e}") from e

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self._session is not None and not self._session.closed:
            asyncio.create_task(self._session.close())
