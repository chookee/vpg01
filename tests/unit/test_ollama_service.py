"""Tests for OllamaService implementation with retry logic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.interfaces.llm_service import LLMService, LLMServiceError
from src.infrastructure.llm.ollama_service import OllamaService


@pytest.fixture
def ollama_service() -> OllamaService:
    """Create OllamaService instance with default settings."""
    return OllamaService()


@pytest.fixture
def sample_context() -> list[Message]:
    """Create sample message context."""
    now = datetime.now(timezone.utc)
    return [
        Message(
            message_id=1,
            session_id=1,
            role="user",
            content="Previous message",
            timestamp=now,
            model_used=None,
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        ),
        Message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Previous response",
            timestamp=now,
            model_used="stub",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        ),
    ]


@pytest.mark.asyncio
async def test_generate_empty_prompt_raises(ollama_service: OllamaService) -> None:
    """Test that empty prompt raises LLMServiceError."""
    with pytest.raises(LLMServiceError, match="Prompt cannot be empty or None"):
        await ollama_service.generate("", [])


@pytest.mark.asyncio
async def test_generate_whitespace_prompt_raises(ollama_service: OllamaService) -> None:
    """Test that whitespace-only prompt raises LLMServiceError."""
    with pytest.raises(LLMServiceError, match="Prompt cannot be empty or None"):
        await ollama_service.generate("   ", [])


@pytest.mark.asyncio
async def test_generate_none_prompt_raises(ollama_service: OllamaService) -> None:
    """Test that None prompt raises LLMServiceError."""
    with pytest.raises(LLMServiceError, match="Prompt cannot be empty or None"):
        await ollama_service.generate(None, [])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_service_base_url_default() -> None:
    """Test default base URL initialization."""
    service = OllamaService()

    assert service.base_url == "http://localhost:11434"


@pytest.mark.asyncio
async def test_service_base_url_custom() -> None:
    """Test custom base URL initialization."""
    custom_url = "http://custom-host:8080"
    service = OllamaService(base_url=custom_url)

    assert service.base_url == custom_url


@pytest.mark.asyncio
async def test_service_default_model() -> None:
    """Test default model initialization."""
    service = OllamaService()

    assert service.default_model == "llama3"


@pytest.mark.asyncio
async def test_service_custom_model() -> None:
    """Test custom model initialization."""
    service = OllamaService(default_model="mistral")

    assert service.default_model == "mistral"


@pytest.mark.asyncio
async def test_inherits_from_llm_service() -> None:
    """Test that OllamaService inherits from LLMService."""
    service = OllamaService()

    assert isinstance(service, LLMService)


@pytest.mark.asyncio
async def test_messages_to_ollama_format(ollama_service: OllamaService) -> None:
    """Test message conversion to Ollama format."""
    now = datetime.now(timezone.utc)
    context = [
        Message(
            message_id=1,
            session_id=1,
            role="user",
            content="Hello",
            timestamp=now,
        ),
        Message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Hi there",
            timestamp=now,
        ),
    ]
    prompt = "How are you?"

    messages = ollama_service._messages_to_ollama_format(prompt, context)

    assert len(messages) == 3
    assert messages[0] == {"role": "user", "content": "Hello"}
    assert messages[1] == {"role": "assistant", "content": "Hi there"}
    assert messages[2] == {"role": "user", "content": "How are you?"}


@pytest.mark.asyncio
async def test_generate_success_mock() -> None:
    """Test successful generation with mocked HTTP client."""
    service = OllamaService()
    prompt = "Test prompt"

    mock_response_data = {
        "message": {"content": "Generated response"},
    }

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = "Generated response"
        result = await service.generate(prompt, [])

        assert result == "Generated response"
        mock_retry.assert_called_once()


@pytest.mark.asyncio
async def test_generate_with_retry_connection_error() -> None:
    """Test retry behavior on connection error."""
    service = OllamaService()
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = aiohttp.ClientConnectionError("Connection failed")

        with pytest.raises(LLMServiceError, match="Ollama generation failed"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_generate_rate_limit_error() -> None:
    """Test rate limit error handling."""
    service = OllamaService()
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = LLMServiceError("Ollama rate limit exceeded")

        with pytest.raises(LLMServiceError, match="rate limit"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_generate_api_error() -> None:
    """Test API error handling."""
    service = OllamaService()
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = LLMServiceError("Ollama API error: 500")

        with pytest.raises(LLMServiceError, match="Ollama API error"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_generate_with_model_params() -> None:
    """Test generation with model parameters."""
    service = OllamaService()
    prompt = "Test with params"
    model_params = {"temperature": 0.7, "max_tokens": 100, "model": "mistral"}

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = "Response"
        await service.generate(prompt, [], model_params)

        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        # Verify model parameter is passed
        assert call_args[0][1] == "mistral"


@pytest.mark.asyncio
async def test_close_session() -> None:
    """Test session cleanup."""
    service = OllamaService()

    # Create session
    await service._get_session()
    assert service._session is not None

    # Close session
    await service.close()
    assert service._session is None or service._session.closed
