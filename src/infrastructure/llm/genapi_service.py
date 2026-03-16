"""GenAPI (gen-api.ru) LLM service implementation with retry logic."""

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


class GenAPIService(LLMService):
    """GenAPI (gen-api.ru) LLM service with HTTP client and retry logic.

    Provides async communication with GenAPI for text generation.
    Supports both sync and async (polling) modes.
    Includes automatic retry on transient failures and timeout handling.

    GenAPI uses non-standard API format:
    - Endpoint: POST /api/v1/networks/{model}
    - Messages content must be array of blocks: [{"type": "text", "text": "..."}]
    - Response may require polling via /api/v1/request/get/{request_id}
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.gen-api.ru/api/v1",
        default_model: str = "gpt-4o-mini",
        timeout: float = 60.0,
        poll_timeout: float = 120.0,
        poll_interval: float = 2.0,
        max_retries: int = 3,
    ) -> None:
        """Initialize GenAPI service.

        Args:
            api_key: GenAPI authentication key.
            base_url: GenAPI base URL. Defaults to production.
            default_model: Default model name for generation.
            timeout: Request timeout in seconds.
            poll_timeout: Maximum polling time for async responses.
            poll_interval: Interval between polling attempts.
            max_retries: Maximum number of retry attempts.
        """
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        self._poll_timeout = poll_timeout
        self._poll_interval = poll_interval
        self._max_retries = max_retries
        self._session: aiohttp.ClientSession | None = None
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @property
    def base_url(self) -> str:
        """Get GenAPI base URL."""
        return self._base_url

    @property
    def default_model(self) -> str:
        """Get default model name."""
        return self._default_model

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._headers,
            )
        return self._session

    async def close(self) -> None:
        """Close aiohttp session."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    def _messages_to_genapi_format(
        self,
        prompt: str,
        context: list[Message],
    ) -> list[dict[str, Any]]:
        """Convert messages to GenAPI format.

        GenAPI requires content as array of blocks:
        [{"type": "text", "text": "..."}]

        Args:
            prompt: Current user prompt.
            context: List of previous messages.

        Returns:
            List of message dicts in GenAPI format.
        """
        messages: list[dict[str, Any]] = []

        # Add context messages
        for msg in context:
            messages.append({
                "role": msg.role,
                "content": [{"type": "text", "text": msg.content}],
            })

        # Add current prompt as user message
        messages.append({
            "role": "user",
            "content": [{"type": "text", "text": prompt}],
        })

        return messages

    def _extract_text_from_response(self, data: dict[str, Any]) -> str:
        """Extract text from GenAPI response.

        GenAPI response structure varies. Check multiple possible locations:
        output, result, data, full_response, response, content

        Args:
            data: Parsed JSON response.

        Returns:
            Extracted text content.
        """
        if not isinstance(data, dict):
            return ""

        candidates = ["output", "result", "data", "full_response", "response", "content"]

        for key in candidates:
            value = data.get(key)
            if not value:
                continue

            if isinstance(value, str):
                return value.strip()

            if isinstance(value, list) and value:
                # Could be list of content blocks or messages
                first = value[0]
                if isinstance(first, dict):
                    # Check for content blocks
                    if "type" in first and first.get("type") == "text":
                        text = first.get("text", "")
                        if text:
                            return text.strip()
                    # Check for message structure
                    if "message" in first:
                        msg = first["message"]
                        if isinstance(msg, dict):
                            content = msg.get("content", "")
                            if isinstance(content, list) and content:
                                block = content[0]
                                if isinstance(block, dict):
                                    return block.get("text", "").strip()
                            elif isinstance(content, str):
                                return content.strip()
                    # Check for choices structure (OpenAI-like)
                    if "choices" in first:
                        choices = first["choices"]
                        if choices and isinstance(choices[0], dict):
                            msg = choices[0].get("message", {})
                            if isinstance(msg, dict):
                                content = msg.get("content", "")
                                if isinstance(content, str):
                                    return content.strip()

            if isinstance(value, dict):
                # Check for OpenAI-like structure
                choices = value.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    msg = choices[0].get("message", {})
                    if isinstance(msg, dict):
                        content = msg.get("content", "")
                        if isinstance(content, str):
                            return content.strip()

        return ""

    async def _poll_for_result(
        self,
        request_id: str,
    ) -> dict[str, Any]:
        """Poll for async result.

        Args:
            request_id: Request identifier from initial response.

        Returns:
            Final response data.

        Raises:
            LLMServiceError: If polling fails or times out.
        """
        url = f"{self._base_url}/request/get/{request_id}"
        max_attempts = int(self._poll_timeout / self._poll_interval)
        session = await self._get_session()

        for attempt in range(max_attempts):
            await asyncio.sleep(self._poll_interval)

            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.debug(
                            "Polling attempt %d: status=%d",
                            attempt + 1,
                            response.status,
                        )
                        continue

                    data = await response.json()
                    status = data.get("status")

                    if status == "success":
                        logger.debug("GenAPI request completed successfully")
                        return data

                    if status == "failed":
                        error_msg = data.get("message", "Unknown error")
                        raise LLMServiceError(f"GenAPI request failed: {error_msg}")

                    logger.debug(
                        "Polling attempt %d: status=%s",
                        attempt + 1,
                        status,
                    )

            except aiohttp.ClientError as e:
                logger.warning("Polling attempt %d failed: %s", attempt + 1, e)
                continue

        raise LLMServiceError(
            f"GenAPI polling timeout after {max_attempts} attempts"
        )

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _generate_with_retry(
        self,
        messages: list[dict[str, Any]],
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
        url = f"{self._base_url}/networks/{model}"
        payload: dict[str, Any] = {
            "messages": messages,
            "is_sync": True,  # Try sync first
            "temperature": model_params.get("temperature", 0.7) if model_params else 0.7,
            "max_tokens": model_params.get("max_tokens", 1500) if model_params else 1500,
        }

        session = await self._get_session()

        try:
            async with session.post(url, json=payload) as response:
                if response.status == 429:
                    raise LLMServiceError("GenAPI rate limit exceeded")

                if response.status != 200:
                    error_text = await response.text()
                    raise LLMServiceError(
                        f"GenAPI error: {response.status} - {error_text}"
                    )

                data = await response.json()

                # Check if response is ready
                if data.get("status") == "success":
                    text = self._extract_text_from_response(data)
                    if not text:
                        raise LLMServiceError("Empty response from GenAPI")
                    return text

                # Async response - need to poll
                request_id = data.get("request_id")
                if not request_id:
                    raise LLMServiceError(
                        f"GenAPI unexpected response: {data}"
                    )

                logger.debug("GenAPI async response, polling for result...")
                result_data = await self._poll_for_result(str(request_id))
                text = self._extract_text_from_response(result_data)

                if not text:
                    raise LLMServiceError("Empty response from GenAPI after polling")

                return text

        except aiohttp.ClientConnectionError as e:
            raise LLMServiceError(f"Cannot connect to GenAPI: {e}") from e
        except asyncio.TimeoutError as e:
            raise LLMServiceError(f"GenAPI request timeout: {e}") from e
        except LLMServiceError:
            raise
        except Exception as e:
            raise LLMServiceError(f"Unexpected GenAPI error: {e}") from e

    async def generate(
        self,
        prompt: str,
        context: list[Message],
        model_params: dict | None = None,
    ) -> str:
        """Generate a response from GenAPI LLM.

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

        messages = self._messages_to_genapi_format(prompt, context)
        model = (
            model_params.get("model", self._default_model)
            if model_params
            else self._default_model
        )

        logger.debug(
            "Generating with GenAPI: model=%s, context_size=%d",
            model,
            len(context),
        )

        try:
            return await self._generate_with_retry(messages, model, model_params)
        except LLMServiceError:
            raise
        except Exception as e:
            raise LLMServiceError(f"GenAPI generation failed: {e}") from e

    def __del__(self) -> None:
        """Cleanup on deletion."""
        if self._session is not None and not self._session.closed:
            asyncio.create_task(self._session.close())
