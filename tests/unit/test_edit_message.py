"""Unit tests for EditMessage use case."""

from datetime import datetime, timezone

import pytest
from pytest_mock import MockerFixture

from src.application.use_cases.edit_message import EditMessage
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, MessageNotFoundError
from src.domain.interfaces.repositories import MessageRepository, SessionStore
from tests.conftest import create_test_message


@pytest.fixture
def mock_message_repo(mocker: MockerFixture) -> MessageRepository:
    """Create mock message repository."""
    return mocker.AsyncMock(spec=MessageRepository)


@pytest.fixture
def mock_short_term_store(mocker: MockerFixture) -> SessionStore:
    """Create mock short-term session store."""
    return mocker.AsyncMock(spec=SessionStore)


@pytest.fixture
def edit_message(
    mock_message_repo: MessageRepository,
    mock_short_term_store: SessionStore,
) -> EditMessage:
    """Create EditMessage use case instance with mocked dependencies."""
    return EditMessage(
        message_repo=mock_message_repo,
        short_term_store=mock_short_term_store,
    )


class TestEditMessageValidation:
    """Test input validation for EditMessage use case."""

    async def test_reject_non_positive_message_id(
        self,
        edit_message: EditMessage,
    ) -> None:
        """Should reject message_id <= 0."""
        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            await edit_message.execute(message_id=0, new_content="New text")

        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            await edit_message.execute(message_id=-10, new_content="New text")

    async def test_reject_empty_new_content(
        self,
        edit_message: EditMessage,
    ) -> None:
        """Should reject empty or whitespace-only new_content."""
        with pytest.raises(InvalidDataError, match="new_content cannot be empty"):
            await edit_message.execute(message_id=1, new_content="")

        with pytest.raises(InvalidDataError, match="new_content cannot be empty"):
            await edit_message.execute(message_id=1, new_content="   ")

    async def test_reject_non_existing_message(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should reject non-existing message."""
        mock_message_repo.get_by_id.return_value = None

        with pytest.raises(MessageNotFoundError, match="Message with id=999 not found"):
            await edit_message.execute(message_id=999, new_content="Updated text")


class TestEditMessageExecution:
    """Test message editing execution."""

    async def test_updates_message_content(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should update message content."""
        original_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="Original text",
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        mock_message_repo.get_by_id.return_value = original_message

        result = await edit_message.execute(
            message_id=42,
            new_content="Updated text",
        )

        assert result.content == "Updated text"
        assert result.message_id == 42
        assert result.session_id == 1
        assert result.role == "user"
        assert result.timestamp == original_message.timestamp

        mock_message_repo.update.assert_called_once()
        updated_msg = mock_message_repo.update.call_args[0][0]
        assert updated_msg.content == "Updated text"

    async def test_preserves_other_message_fields(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should preserve all other message fields."""
        original_message = Message(
            message_id=10,
            session_id=5,
            role="assistant",
            content="Old content",
            timestamp=datetime(2024, 6, 15, 10, 30, tzinfo=timezone.utc),
            model_used="llama3",
            memory_mode_at_time=MemoryMode.BOTH,
        )
        mock_message_repo.get_by_id.return_value = original_message

        result = await edit_message.execute(
            message_id=10,
            new_content="New content",
        )

        assert result.message_id == original_message.message_id
        assert result.session_id == original_message.session_id
        assert result.role == original_message.role
        assert result.timestamp == original_message.timestamp
        assert result.model_used == original_message.model_used
        assert result.memory_mode_at_time == original_message.memory_mode_at_time
        assert result.content == "New content"

    async def test_updates_user_message(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should update user message."""
        user_message = create_test_message(
            message_id=1,
            session_id=1,
            role="user",
            content="User original",
        )
        mock_message_repo.get_by_id.return_value = user_message

        result = await edit_message.execute(message_id=1, new_content="User updated")

        assert result.role == "user"
        assert result.content == "User updated"

    async def test_updates_assistant_message(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should update assistant message."""
        assistant_message = create_test_message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Assistant original",
            model_used="gpt-4",
        )
        mock_message_repo.get_by_id.return_value = assistant_message

        result = await edit_message.execute(
            message_id=2,
            new_content="Assistant updated",
        )

        assert result.role == "assistant"
        assert result.content == "Assistant updated"
        assert result.model_used == "gpt-4"

    async def test_searches_across_all_sessions(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should find message across all sessions."""
        target_message = create_test_message(
            message_id=2,
            session_id=2,
            role="assistant",
            content="Session 2 msg 1",
        )
        mock_message_repo.get_by_id.return_value = target_message

        result = await edit_message.execute(message_id=2, new_content="Updated")

        assert result.content == "Updated"
        assert result.session_id == 2

    async def test_updates_short_term_store(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should update message in short-term store if it exists there."""
        original_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="Original text",
        )
        mock_message_repo.get_by_id.return_value = original_message
        mock_short_term_store.update_message.return_value = True

        result = await edit_message.execute(message_id=42, new_content="Updated text")

        # Verify short-term store was called
        mock_short_term_store.update_message.assert_called_once()
        updated_msg = mock_short_term_store.update_message.call_args[0][0]
        assert updated_msg.content == "Updated text"
        assert updated_msg.message_id == 42

    async def test_handles_short_term_store_failure_gracefully(
        self,
        edit_message: EditMessage,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should complete successfully even if short-term store update fails."""
        original_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="Original text",
        )
        mock_message_repo.get_by_id.return_value = original_message
        mock_short_term_store.update_message.side_effect = Exception("Store unavailable")

        # Should not raise exception
        result = await edit_message.execute(message_id=42, new_content="Updated text")

        assert result.content == "Updated text"
        mock_message_repo.update.assert_called_once()
