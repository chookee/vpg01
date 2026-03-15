"""Tests for OllamaService stub implementation."""

from datetime import datetime, timezone

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
async def test_generate_returns_echo(ollama_service: OllamaService) -> None:
    """Test that generate returns echo response."""
    prompt = "Hello, World!"
    context: list[Message] = []

    result = await ollama_service.generate(prompt, context)

    assert result == "Echo: Hello, World!"


@pytest.mark.asyncio
async def test_generate_with_context(
    ollama_service: OllamaService,
    sample_context: list[Message],
) -> None:
    """Test that generate works with context messages."""
    prompt = "Test with context"

    result = await ollama_service.generate(prompt, sample_context)

    assert result == "Echo: Test with context"


@pytest.mark.asyncio
async def test_generate_with_model_params(ollama_service: OllamaService) -> None:
    """Test that generate accepts model parameters."""
    prompt = "Test with params"
    model_params = {"temperature": 0.7, "max_tokens": 100}

    result = await ollama_service.generate(prompt, [], model_params)

    assert result == "Echo: Test with params"


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
async def test_generate_with_special_characters(ollama_service: OllamaService) -> None:
    """Test that generate handles special characters."""
    prompt = "Test with special chars: !@#$%^&*()_+{}|:<>?"

    result = await ollama_service.generate(prompt, [])

    assert result == "Echo: Test with special chars: !@#$%^&*()_+{}|:<>?"


@pytest.mark.asyncio
async def test_generate_with_unicode(ollama_service: OllamaService) -> None:
    """Test that generate handles Unicode characters."""
    prompt = "Привет, мир! 你好世界 🌍"

    result = await ollama_service.generate(prompt, [])

    assert result == "Echo: Привет, мир! 你好世界 🌍"


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
