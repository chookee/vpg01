"""Unit tests for ProcessMessage use case."""

import pytest
from pytest_mock import MockerFixture

from src.application.dtos import SessionDTO
from src.application.services.context_builder import ContextBuilder
from src.application.use_cases.process_message import (
    ProcessMessage,
    ProcessMessageResult,
)
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, SessionNotFoundError
from src.domain.interfaces.llm_service import LLMService
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    SessionStore,
)
from tests.conftest import create_test_message, create_test_session_dto


@pytest.fixture
def mock_message_repo(mocker: MockerFixture) -> MessageRepository:
    """Create mock message repository."""
    return mocker.AsyncMock(spec=MessageRepository)


@pytest.fixture
def mock_session_repo(mocker: MockerFixture) -> SessionRepository:
    """Create mock session repository."""
    return mocker.AsyncMock(spec=SessionRepository)


@pytest.fixture
def mock_short_term_store(mocker: MockerFixture) -> SessionStore:
    """Create mock short-term session store."""
    return mocker.AsyncMock(spec=SessionStore)


@pytest.fixture
def mock_context_builder(mocker: MockerFixture) -> ContextBuilder:
    """Create mock context builder."""
    return mocker.AsyncMock(spec=ContextBuilder)


@pytest.fixture
def mock_llm_service(mocker: MockerFixture) -> LLMService:
    """Create mock LLM service."""
    return mocker.AsyncMock(spec=LLMService)


@pytest.fixture
def process_message(
    mock_message_repo: MessageRepository,
    mock_session_repo: SessionRepository,
    mock_short_term_store: SessionStore,
    mock_context_builder: ContextBuilder,
    mock_llm_service: LLMService,
) -> ProcessMessage:
    """Create ProcessMessage use case instance with mocked dependencies."""
    return ProcessMessage(
        message_repo=mock_message_repo,
        session_repo=mock_session_repo,
        short_term_store=mock_short_term_store,
        context_builder=mock_context_builder,
        llm_service=mock_llm_service,
        default_model="test-model",
    )


class TestProcessMessageValidation:
    """Test input validation for ProcessMessage use case."""

    async def test_reject_non_positive_session_id(
        self,
        process_message: ProcessMessage,
    ) -> None:
        """Should reject session_id <= 0."""
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            await process_message.execute(session_id=0, user_text="Hello")

        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            await process_message.execute(session_id=-1, user_text="Hello")

    async def test_reject_empty_user_text(
        self,
        process_message: ProcessMessage,
    ) -> None:
        """Should reject empty or whitespace-only user_text."""
        with pytest.raises(InvalidDataError, match="user_text cannot be empty"):
            await process_message.execute(session_id=1, user_text="")

        with pytest.raises(InvalidDataError, match="user_text cannot be empty"):
            await process_message.execute(session_id=1, user_text="   ")

    async def test_reject_non_existing_session(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
    ) -> None:
        """Should reject non-existing session."""
        mock_session_repo.get.return_value = None

        with pytest.raises(SessionNotFoundError, match="Session with id=999 not found"):
            await process_message.execute(session_id=999, user_text="Hello")


class TestProcessMessageNoMemoryMode:
    """Test ProcessMessage with NO_MEMORY mode."""

    async def test_no_messages_saved_in_no_memory_mode(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should not save messages in NO_MEMORY mode."""
        session = create_test_session_dto(mode=MemoryMode.NO_MEMORY)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Echo: Test"

        result = await process_message.execute(session_id=1, user_text="Test")

        assert isinstance(result, ProcessMessageResult)
        assert result.response == "Echo: Test"

        mock_message_repo.add.assert_not_called()
        mock_short_term_store.add_message.assert_not_called()


class TestProcessMessageShortTermMode:
    """Test ProcessMessage with SHORT_TERM mode."""

    async def test_messages_saved_to_short_term_only(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should save messages to short-term store only in SHORT_TERM mode."""
        session = create_test_session_dto(mode=MemoryMode.SHORT_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Echo: Hello"
        # Mock add_message to return assigned IDs (positive integers)
        mock_short_term_store.add_message.side_effect = [1, 2]

        result = await process_message.execute(session_id=1, user_text="Hello")

        assert result.response == "Echo: Hello"
        assert result.user_message.message_id == 1
        assert result.assistant_message.message_id == 2

        mock_message_repo.add.assert_not_called()
        assert mock_short_term_store.add_message.call_count == 2


class TestProcessMessageLongTermMode:
    """Test ProcessMessage with LONG_TERM mode."""

    async def test_messages_saved_to_long_term_only(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should save messages to long-term repo only in LONG_TERM mode."""
        session = create_test_session_dto(mode=MemoryMode.LONG_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Echo: World"
        # Mock add to return assigned IDs
        mock_message_repo.add.side_effect = [1, 2]

        result = await process_message.execute(session_id=1, user_text="World")

        assert result.response == "Echo: World"
        assert result.user_message.message_id == 1
        assert result.assistant_message.message_id == 2

        assert mock_message_repo.add.call_count == 2
        mock_short_term_store.add_message.assert_not_called()


class TestProcessMessageBothMode:
    """Test ProcessMessage with BOTH mode."""

    async def test_messages_saved_to_both_stores(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should save messages to both stores in BOTH mode."""
        session = create_test_session_dto(mode=MemoryMode.BOTH)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Echo: Both"
        # Mock add to return assigned IDs
        mock_message_repo.add.side_effect = [1, 2]
        mock_short_term_store.add_message.side_effect = [1, 2]

        result = await process_message.execute(session_id=1, user_text="Both")

        assert result.response == "Echo: Both"
        assert result.user_message.message_id == 1
        assert result.assistant_message.message_id == 2

        assert mock_message_repo.add.call_count == 2
        assert mock_short_term_store.add_message.call_count == 2

    async def test_context_builder_called_with_correct_mode(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should call context builder with session's memory mode."""
        session = create_test_session_dto(mode=MemoryMode.BOTH)
        mock_session_repo.get.return_value = session
        mock_llm_service.generate.return_value = "Response"
        # Mock add to return assigned IDs
        mock_message_repo.add.side_effect = [1, 2]
        mock_short_term_store.add_message.side_effect = [1, 2]

        await process_message.execute(session_id=1, user_text="Test")

        mock_context_builder.build_context.assert_called_once_with(
            session_id=1,
            mode=MemoryMode.BOTH,
        )

    async def test_mode_override_takes_precedence(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
    ) -> None:
        """Should use provided mode override instead of session's mode."""
        session = create_test_session_dto(mode=MemoryMode.LONG_TERM)
        mock_session_repo.get.return_value = session
        mock_llm_service.generate.return_value = "Response"

        await process_message.execute(
            session_id=1,
            user_text="Test",
            mode=MemoryMode.NO_MEMORY,
        )

        mock_context_builder.build_context.assert_called_once_with(
            session_id=1,
            mode=MemoryMode.NO_MEMORY,
        )


class TestProcessMessageResult:
    """Test ProcessMessage result structure."""

    async def test_returns_correct_result_structure(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should return ProcessMessageResult with all required fields."""
        session = create_test_session_dto(mode=MemoryMode.SHORT_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Test response"
        # Mock add_message to return assigned IDs
        mock_short_term_store.add_message.side_effect = [1, 2]

        result = await process_message.execute(session_id=1, user_text="Hello")

        assert isinstance(result, ProcessMessageResult)
        assert result.response == "Test response"
        assert isinstance(result.user_message, Message)
        assert isinstance(result.assistant_message, Message)
        assert result.user_message.role == "user"
        assert result.assistant_message.role == "assistant"
        assert result.user_message.content == "Hello"
        assert result.assistant_message.content == "Test response"
        assert result.user_message.message_id == 1
        assert result.assistant_message.message_id == 2

    async def test_returns_messages_with_assigned_ids(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should return messages with assigned IDs from repository."""
        from datetime import datetime, timezone

        session = create_test_session_dto(mode=MemoryMode.LONG_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.return_value = "Test response"

        # Mock add to return assigned IDs
        mock_message_repo.add.side_effect = [1, 2]

        result = await process_message.execute(session_id=1, user_text="Hello")

        assert result.user_message.message_id == 1
        assert result.assistant_message.message_id == 2

    async def test_llm_error_handling(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
    ) -> None:
        """Should handle LLM service errors gracefully."""
        from src.domain.exceptions import LLMServiceError

        session = create_test_session_dto(mode=MemoryMode.SHORT_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.side_effect = LLMServiceError("LLM unavailable")

        with pytest.raises(LLMServiceError, match="LLM service error"):
            await process_message.execute(session_id=1, user_text="Hello")

    async def test_unexpected_error_wrapped_in_llm_service_error(
        self,
        process_message: ProcessMessage,
        mock_session_repo: SessionRepository,
        mock_context_builder: ContextBuilder,
        mock_llm_service: LLMService,
    ) -> None:
        """Should wrap unexpected errors in LLMServiceError."""
        from src.domain.exceptions import LLMServiceError

        session = create_test_session_dto(mode=MemoryMode.SHORT_TERM)
        mock_session_repo.get.return_value = session
        mock_context_builder.build_context.return_value = []
        mock_llm_service.generate.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(LLMServiceError, match="Failed to generate response"):
            await process_message.execute(session_id=1, user_text="Hello")
