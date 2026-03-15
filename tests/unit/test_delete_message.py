"""Unit tests for DeleteMessage use case."""

import pytest
from pytest_mock import MockerFixture

from src.application.use_cases.delete_message import DeleteMessage
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
def delete_message(
    mock_message_repo: MessageRepository,
    mock_short_term_store: SessionStore,
) -> DeleteMessage:
    """Create DeleteMessage use case instance with mocked dependencies."""
    return DeleteMessage(
        message_repo=mock_message_repo,
        short_term_store=mock_short_term_store,
    )


class TestDeleteMessageValidation:
    """Test input validation for DeleteMessage use case."""

    async def test_reject_non_positive_message_id(
        self,
        delete_message: DeleteMessage,
    ) -> None:
        """Should reject message_id <= 0."""
        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            await delete_message.execute(message_id=0)

        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            await delete_message.execute(message_id=-42)

    async def test_reject_non_existing_message(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should reject non-existing message."""
        mock_message_repo.get_by_id.return_value = None

        with pytest.raises(MessageNotFoundError, match="Message with id=999 not found"):
            await delete_message.execute(message_id=999)


class TestDeleteMessageExecution:
    """Test message deletion execution."""

    async def test_deletes_existing_message(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should delete existing message."""
        existing_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="To be deleted",
        )
        mock_message_repo.get_by_id.return_value = existing_message

        await delete_message.execute(message_id=42)

        mock_message_repo.delete.assert_called_once_with(42)

    async def test_deletes_user_message(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should delete user message."""
        user_message = create_test_message(
            message_id=1,
            session_id=1,
            role="user",
            content="User message",
        )
        mock_message_repo.get_by_id.return_value = user_message

        await delete_message.execute(message_id=1)

        mock_message_repo.delete.assert_called_once_with(1)

    async def test_deletes_assistant_message(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should delete assistant message."""
        assistant_message = create_test_message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Assistant message",
            model_used="llama3",
        )
        mock_message_repo.get_by_id.return_value = assistant_message

        await delete_message.execute(message_id=2)

        mock_message_repo.delete.assert_called_once_with(2)

    async def test_deletes_message_from_correct_session(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should delete message from correct session."""
        target_message = create_test_message(
            message_id=2,
            session_id=2,
            role="user",
            content="Session 2",
        )
        mock_message_repo.get_by_id.return_value = target_message

        await delete_message.execute(message_id=2)

        mock_message_repo.delete.assert_called_once_with(2)

    async def test_does_not_delete_other_messages(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should not affect other messages."""
        target_message = create_test_message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Msg 2",
        )
        mock_message_repo.get_by_id.return_value = target_message

        await delete_message.execute(message_id=2)

        mock_message_repo.delete.assert_called_once_with(2)

    async def test_returns_none_after_deletion(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
    ) -> None:
        """Should return None after successful deletion."""
        existing_message = create_test_message(
            message_id=5,
            session_id=1,
            role="user",
            content="Delete me",
        )
        mock_message_repo.get_by_id.return_value = existing_message

        result = await delete_message.execute(message_id=5)

        assert result is None

    async def test_deletes_from_short_term_store(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should delete message from short-term store."""
        existing_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="To be deleted",
        )
        mock_message_repo.get_by_id.return_value = existing_message
        mock_short_term_store.delete_message.return_value = True

        await delete_message.execute(message_id=42)

        mock_short_term_store.delete_message.assert_called_once_with(42, 1)

    async def test_handles_short_term_store_failure_gracefully(
        self,
        delete_message: DeleteMessage,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should complete successfully even if short-term store delete fails."""
        existing_message = create_test_message(
            message_id=42,
            session_id=1,
            role="user",
            content="To be deleted",
        )
        mock_message_repo.get_by_id.return_value = existing_message
        mock_short_term_store.delete_message.side_effect = Exception("Store unavailable")

        # Should not raise exception
        await delete_message.execute(message_id=42)

        mock_message_repo.delete.assert_called_once_with(42)
