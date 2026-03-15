"""Unit tests for ViewHistory use case."""

import pytest
from pytest_mock import MockerFixture

from src.application.use_cases.view_history import ViewHistory
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, SessionNotFoundError
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
def view_history(
    mock_message_repo: MessageRepository,
    mock_session_repo: SessionRepository,
    mock_short_term_store: SessionStore,
) -> ViewHistory:
    """Create ViewHistory use case instance with mocked dependencies."""
    return ViewHistory(
        message_repo=mock_message_repo,
        session_repo=mock_session_repo,
        short_term_store=mock_short_term_store,
    )


class TestViewHistoryValidation:
    """Test input validation for ViewHistory use case."""

    async def test_reject_non_positive_session_id(
        self,
        view_history: ViewHistory,
    ) -> None:
        """Should reject session_id <= 0."""
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            await view_history.execute(session_id=0)

        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            await view_history.execute(session_id=-5)

    async def test_reject_non_existing_session(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
    ) -> None:
        """Should reject non-existing session."""
        mock_session_repo.get.return_value = None

        with pytest.raises(SessionNotFoundError, match="Session with id=999 not found"):
            await view_history.execute(session_id=999)


class TestViewHistoryRetrieval:
    """Test message retrieval for ViewHistory use case."""

    async def test_returns_empty_list_for_session_without_messages(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should return empty list for session with no messages."""
        session = create_test_session_dto(mode=MemoryMode.SHORT_TERM)
        mock_session_repo.get.return_value = session
        mock_message_repo.get_by_session.return_value = []
        mock_short_term_store.get_messages.return_value = []

        result = await view_history.execute(session_id=1)

        assert result == []
        mock_message_repo.get_by_session.assert_called_once_with(1)
        mock_short_term_store.get_messages.assert_called_once_with(1)

    async def test_returns_messages_sorted_by_timestamp(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should return messages sorted by timestamp."""
        from datetime import datetime, timezone

        session = create_test_session_dto(mode=MemoryMode.LONG_TERM)
        mock_session_repo.get.return_value = session

        messages = [
            create_test_message(
                message_id=1,
                session_id=1,
                role="user",
                content="First",
                timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            ),
            create_test_message(
                message_id=2,
                session_id=1,
                role="assistant",
                content="Second",
                timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
            ),
            create_test_message(
                message_id=3,
                session_id=1,
                role="user",
                content="Third",
                timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            ),
        ]
        mock_message_repo.get_by_session.return_value = messages
        mock_short_term_store.get_messages.return_value = []

        result = await view_history.execute(session_id=1)

        assert len(result) == 3
        assert result[0].content == "First"
        assert result[1].content == "Second"
        assert result[2].content == "Third"

    async def test_returns_all_messages_for_session(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should return all messages for a session."""
        session = create_test_session_dto(mode=MemoryMode.BOTH)
        mock_session_repo.get.return_value = session

        messages = [
            create_test_message(message_id=i, session_id=1, role="user", content=f"Msg {i}")
            for i in range(1, 6)
        ]
        mock_message_repo.get_by_session.return_value = messages
        mock_short_term_store.get_messages.return_value = []

        result = await view_history.execute(session_id=1)

        assert len(result) == 5
        assert all(msg.session_id == 1 for msg in result)

    async def test_merges_messages_from_both_stores(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should merge messages from both long-term and short-term stores."""
        from datetime import datetime, timezone

        session = create_test_session_dto(mode=MemoryMode.BOTH)
        mock_session_repo.get.return_value = session

        # Messages from long-term store (database)
        long_term_msgs = [
            create_test_message(
                message_id=1,
                session_id=1,
                role="user",
                content="DB Msg 1",
                timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
            ),
            create_test_message(
                message_id=3,
                session_id=1,
                role="user",
                content="DB Msg 3",
                timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            ),
        ]

        # Messages from short-term store (in-memory)
        short_term_msgs = [
            create_test_message(
                message_id=2,
                session_id=1,
                role="assistant",
                content="Memory Msg 2",
                timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
            ),
        ]

        mock_message_repo.get_by_session.return_value = long_term_msgs
        mock_short_term_store.get_messages.return_value = short_term_msgs

        result = await view_history.execute(session_id=1)

        # Should have all 3 messages merged and sorted
        assert len(result) == 3
        assert result[0].content == "DB Msg 1"
        assert result[1].content == "Memory Msg 2"
        assert result[2].content == "DB Msg 3"

    async def test_removes_duplicates_when_merging(
        self,
        view_history: ViewHistory,
        mock_session_repo: SessionRepository,
        mock_message_repo: MessageRepository,
        mock_short_term_store: SessionStore,
    ) -> None:
        """Should remove duplicates by message_id when merging."""
        from datetime import datetime, timezone

        session = create_test_session_dto(mode=MemoryMode.BOTH)
        mock_session_repo.get.return_value = session

        # Same message in both stores (should be deduplicated)
        shared_msg = create_test_message(
            message_id=1,
            session_id=1,
            role="user",
            content="Shared Msg",
            timestamp=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
        )

        mock_message_repo.get_by_session.return_value = [shared_msg]
        mock_short_term_store.get_messages.return_value = [shared_msg]

        result = await view_history.execute(session_id=1)

        # Should have only 1 message (deduplicated)
        assert len(result) == 1
        assert result[0].message_id == 1
