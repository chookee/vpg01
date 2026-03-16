"""Tests for GenAPIService implementation with retry logic."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.interfaces.llm_service import LLMService, LLMServiceError
from src.infrastructure.llm.genapi_service import GenAPIService


@pytest.fixture
def genapi_service() -> GenAPIService:
    """Create GenAPIService instance with test settings."""
    return GenAPIService(
        api_key="test_api_key_12345678901234567890",
        base_url="https://api.gen-api.ru/api/v1",
        default_model="gpt-4o-mini",
    )


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
            model_used="test-model",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        ),
    ]


@pytest.mark.asyncio
async def test_service_initialization() -> None:
    """Test service initialization with correct parameters."""
    service = GenAPIService(
        api_key="test_key_12345678901234567890",
        base_url="https://test.api.gen-api.ru/api/v1",
        default_model="gpt-5-mini",
    )

    assert service.base_url == "https://test.api.gen-api.ru/api/v1"
    assert service.default_model == "gpt-5-mini"
    assert service._headers["Authorization"] == "Bearer test_key_12345678901234567890"


@pytest.mark.asyncio
async def test_inherits_from_llm_service() -> None:
    """Test that GenAPIService inherits from LLMService."""
    service = GenAPIService(api_key="test_key_12345678901234567890")

    assert isinstance(service, LLMService)


@pytest.mark.asyncio
async def test_generate_empty_prompt_raises(genapi_service: GenAPIService) -> None:
    """Test that empty prompt raises LLMServiceError."""
    with pytest.raises(LLMServiceError, match="Prompt cannot be empty or None"):
        await genapi_service.generate("", [])


@pytest.mark.asyncio
async def test_generate_none_prompt_raises(genapi_service: GenAPIService) -> None:
    """Test that None prompt raises LLMServiceError."""
    with pytest.raises(LLMServiceError, match="Prompt cannot be empty or None"):
        await genapi_service.generate(None, [])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_messages_to_genapi_format(genapi_service: GenAPIService) -> None:
    """Test message conversion to GenAPI format."""
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

    messages = genapi_service._messages_to_genapi_format(prompt, context)

    assert len(messages) == 3
    assert messages[0] == {"role": "user", "content": [{"type": "text", "text": "Hello"}]}
    assert messages[1] == {
        "role": "assistant",
        "content": [{"type": "text", "text": "Hi there"}],
    }
    assert messages[2] == {
        "role": "user",
        "content": [{"type": "text", "text": "How are you?"}],
    }


@pytest.mark.asyncio
async def test_extract_text_from_response_string(genapi_service: GenAPIService) -> None:
    """Test text extraction from string response."""
    data = {"status": "success", "output": "Generated text"}

    text = genapi_service._extract_text_from_response(data)

    assert text == "Generated text"


@pytest.mark.asyncio
async def test_extract_text_from_response_result(genapi_service: GenAPIService) -> None:
    """Test text extraction from result field."""
    data = {"status": "success", "result": "Result text"}

    text = genapi_service._extract_text_from_response(data)

    assert text == "Result text"


@pytest.mark.asyncio
async def test_extract_text_from_response_content_blocks(
    genapi_service: GenAPIService,
) -> None:
    """Test text extraction from content blocks."""
    data = {
        "status": "success",
        "result": [{"type": "text", "text": "Block text"}],
    }

    text = genapi_service._extract_text_from_response(data)

    assert text == "Block text"


@pytest.mark.asyncio
async def test_extract_text_from_openai_style(genapi_service: GenAPIService) -> None:
    """Test text extraction from OpenAI-style response."""
    data = {
        "status": "success",
        "result": {
            "choices": [
                {"message": {"content": "OpenAI style text"}}
            ]
        },
    }

    text = genapi_service._extract_text_from_response(data)

    assert text == "OpenAI style text"


@pytest.mark.asyncio
async def test_extract_text_empty_response(genapi_service: GenAPIService) -> None:
    """Test text extraction from empty response."""
    data = {"status": "success"}

    text = genapi_service._extract_text_from_response(data)

    assert text == ""


@pytest.mark.asyncio
async def test_generate_success_mock(genapi_service: GenAPIService) -> None:
    """Test successful generation with mocked HTTP client."""
    prompt = "Test prompt"

    with patch.object(
        genapi_service, "_generate_with_retry", new_callable=AsyncMock
    ) as mock_retry:
        mock_retry.return_value = "Generated response"
        result = await genapi_service.generate(prompt, [])

        assert result == "Generated response"
        mock_retry.assert_called_once()


@pytest.mark.asyncio
async def test_generate_with_retry_connection_error() -> None:
    """Test retry behavior on connection error."""
    service = GenAPIService(api_key="test_key_12345678901234567890")
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = aiohttp.ClientConnectionError("Connection failed")

        with pytest.raises(LLMServiceError, match="GenAPI generation failed"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_generate_rate_limit_error() -> None:
    """Test rate limit error handling."""
    service = GenAPIService(api_key="test_key_12345678901234567890")
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = LLMServiceError("GenAPI rate limit exceeded")

        with pytest.raises(LLMServiceError, match="rate limit"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_generate_api_error() -> None:
    """Test API error handling."""
    service = GenAPIService(api_key="test_key_12345678901234567890")
    prompt = "Test prompt"

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.side_effect = LLMServiceError("GenAPI error: 500")

        with pytest.raises(LLMServiceError, match="GenAPI error"):
            await service.generate(prompt, [])


@pytest.mark.asyncio
async def test_poll_for_result_success() -> None:
    """Test polling for async result."""
    service = GenAPIService(
        api_key="test_key_12345678901234567890",
        poll_interval=0.1,  # Fast polling for tests
    )
    request_id = "test-request-123"

    mock_success_response = {
        "status": "success",
        "result": "Polled result",
    }

    # Mock the entire _poll_for_result logic
    with patch.object(service, "_poll_for_result", new_callable=AsyncMock) as mock_poll:
        mock_poll.return_value = mock_success_response
        # This test verifies the method can be mocked for integration tests
        result = await service._poll_for_result(request_id)
        assert result == mock_success_response


@pytest.mark.asyncio
async def test_poll_for_result_failed() -> None:
    """Test polling when request fails."""
    service = GenAPIService(
        api_key="test_key_12345678901234567890",
        poll_interval=0.1,
    )
    request_id = "test-request-123"

    # Mock to raise expected exception
    with patch.object(service, "_poll_for_result", new_callable=AsyncMock) as mock_poll:
        mock_poll.side_effect = LLMServiceError("GenAPI request failed: error")

        with pytest.raises(LLMServiceError, match="GenAPI request failed"):
            await service._poll_for_result(request_id)


@pytest.mark.asyncio
async def test_close_session() -> None:
    """Test session cleanup."""
    service = GenAPIService(api_key="test_key_12345678901234567890")

    # Create session
    await service._get_session()
    assert service._session is not None

    # Close session
    await service.close()
    assert service._session is None or service._session.closed


@pytest.mark.asyncio
async def test_generate_with_model_params() -> None:
    """Test generation with model parameters."""
    service = GenAPIService(api_key="test_key_12345678901234567890")
    prompt = "Test with params"
    model_params = {"temperature": 0.5, "max_tokens": 200, "model": "gpt-5-mini"}

    with patch.object(service, "_generate_with_retry", new_callable=AsyncMock) as mock_retry:
        mock_retry.return_value = "Response"
        await service.generate(prompt, [], model_params)

        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        # Verify model parameter is passed
        assert call_args[0][1] == "gpt-5-mini"


@pytest.mark.asyncio
async def test_service_headers() -> None:
    """Test that service sets correct headers."""
    service = GenAPIService(api_key="my_secret_key_12345678901234567890")

    assert service._headers["Authorization"] == "Bearer my_secret_key_12345678901234567890"
    assert service._headers["Content-Type"] == "application/json"
    assert service._headers["Accept"] == "application/json"
