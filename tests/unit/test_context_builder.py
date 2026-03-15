"""Unit tests for ContextBuilder service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.context_builder import ContextBuilder
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError


@pytest.fixture
def mock_message_repo() -> MagicMock:
    """Create mock message repository."""
    repo = MagicMock(spec=["get_by_session"])
    repo.get_by_session = AsyncMock()
    return repo


@pytest.fixture
def mock_session_store() -> MagicMock:
    """Create mock short-term session store."""
    store = MagicMock(spec=["get_messages", "add_message", "clear_session", "get_session"])
    store.get_messages = AsyncMock()
    store.add_message = AsyncMock()
    store.clear_session = AsyncMock()
    store.get_session = AsyncMock()
    return store


@pytest.fixture
def context_builder(
    mock_message_repo: MagicMock,
    mock_session_store: MagicMock,
) -> ContextBuilder:
    """Create ContextBuilder instance with mocked dependencies."""
    return ContextBuilder(
        long_term_repo=mock_message_repo,
        short_term_store=mock_session_store,
    )


def create_test_message(
    message_id: int,
    session_id: int,
    role: str = "user",
    content: str = "Test message",
    timestamp: datetime | None = None,
) -> Message:
    """Helper to create test messages."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return Message(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        timestamp=timestamp,
    )


@pytest.mark.asyncio
async def test_no_memory_mode_returns_empty_list(
    context_builder: ContextBuilder,
) -> None:
    """Test that NO_MEMORY mode returns empty context."""
    session_id = 1
    mode = MemoryMode.NO_MEMORY

    result = await context_builder.build_context(session_id, mode)

    assert result == []


@pytest.mark.asyncio
async def test_short_term_mode_returns_memory_messages(
    context_builder: ContextBuilder,
    mock_session_store: MagicMock,
) -> None:
    """Test that SHORT_TERM mode returns messages from memory."""
    session_id = 1
    mode = MemoryMode.SHORT_TERM

    msg1 = create_test_message(1, session_id, "user", "Hello")
    msg2 = create_test_message(2, session_id, "assistant", "Hi there")

    mock_session_store.get_messages.return_value = [msg1, msg2]

    result = await context_builder.build_context(session_id, mode)

    assert len(result) == 2
    assert result[0].message_id == 1
    assert result[1].message_id == 2
    mock_session_store.get_messages.assert_called_once_with(session_id)


@pytest.mark.asyncio
async def test_long_term_mode_returns_db_messages(
    context_builder: ContextBuilder,
    mock_message_repo: MagicMock,
) -> None:
    """Test that LONG_TERM mode returns messages from database."""
    session_id = 1
    mode = MemoryMode.LONG_TERM

    msg1 = create_test_message(1, session_id, "user", "Hello from DB")
    msg2 = create_test_message(2, session_id, "assistant", "Response from DB")

    mock_message_repo.get_by_session.return_value = [msg1, msg2]

    result = await context_builder.build_context(session_id, mode)

    assert len(result) == 2
    assert result[0].content == "Hello from DB"
    assert result[1].content == "Response from DB"
    mock_message_repo.get_by_session.assert_called_once_with(session_id)


@pytest.mark.asyncio
async def test_both_mode_merges_messages(
    context_builder: ContextBuilder,
    mock_session_store: MagicMock,
    mock_message_repo: MagicMock,
) -> None:
    """Test that BOTH mode merges messages from both sources."""
    session_id = 1
    mode = MemoryMode.BOTH

    base_time = datetime.now(timezone.utc)

    db_msg1 = create_test_message(
        1, session_id, "user", "DB message 1", base_time
    )
    db_msg2 = create_test_message(
        2, session_id, "assistant", "DB message 2", base_time
    )
    mem_msg1 = create_test_message(
        3, session_id, "user", "Memory message 1", base_time
    )
    mem_msg2 = create_test_message(
        4, session_id, "assistant", "Memory message 2", base_time
    )

    mock_message_repo.get_by_session.return_value = [db_msg1, db_msg2]
    mock_session_store.get_messages.return_value = [mem_msg1, mem_msg2]

    result = await context_builder.build_context(session_id, mode)

    assert len(result) == 4
    message_ids = {msg.message_id for msg in result}
    assert message_ids == {1, 2, 3, 4}


@pytest.mark.asyncio
async def test_both_mode_removes_duplicates(
    context_builder: ContextBuilder,
    mock_session_store: MagicMock,
    mock_message_repo: MagicMock,
) -> None:
    """Test that BOTH mode removes duplicate messages by ID."""
    session_id = 1
    mode = MemoryMode.BOTH

    base_time = datetime.now(timezone.utc)

    db_msg = create_test_message(
        1, session_id, "user", "DB version", base_time
    )
    mem_msg = create_test_message(
        1, session_id, "user", "Memory version", base_time
    )

    mock_message_repo.get_by_session.return_value = [db_msg]
    mock_session_store.get_messages.return_value = [mem_msg]

    result = await context_builder.build_context(session_id, mode)

    assert len(result) == 1
    assert result[0].message_id == 1


@pytest.mark.asyncio
async def test_both_mode_sorts_by_timestamp(
    context_builder: ContextBuilder,
    mock_session_store: MagicMock,
    mock_message_repo: MagicMock,
) -> None:
    """Test that BOTH mode sorts merged messages by timestamp."""
    session_id = 1
    mode = MemoryMode.BOTH

    base_time = datetime.now(timezone.utc)

    msg1 = create_test_message(
        1, session_id, "user", "First", base_time.replace(second=1)
    )
    msg2 = create_test_message(
        2, session_id, "assistant", "Second", base_time.replace(second=2)
    )
    msg3 = create_test_message(
        3, session_id, "user", "Third", base_time.replace(second=3)
    )

    mock_message_repo.get_by_session.return_value = [msg1, msg3]
    mock_session_store.get_messages.return_value = [msg2]

    result = await context_builder.build_context(session_id, mode)

    assert len(result) == 3
    assert result[0].content == "First"
    assert result[1].content == "Second"
    assert result[2].content == "Third"


@pytest.mark.asyncio
async def test_short_term_empty_session_returns_empty(
    context_builder: ContextBuilder,
    mock_session_store: MagicMock,
) -> None:
    """Test SHORT_TERM mode with non-existent session."""
    session_id = 999
    mode = MemoryMode.SHORT_TERM

    mock_session_store.get_messages.return_value = []

    result = await context_builder.build_context(session_id, mode)

    assert result == []


@pytest.mark.asyncio
async def test_long_term_empty_session_returns_empty(
    context_builder: ContextBuilder,
    mock_message_repo: MagicMock,
) -> None:
    """Test LONG_TERM mode with non-existent session."""
    session_id = 999
    mode = MemoryMode.LONG_TERM

    mock_message_repo.get_by_session.return_value = []

    result = await context_builder.build_context(session_id, mode)

    assert result == []


@pytest.mark.asyncio
async def test_invalid_session_id_raises_error(
    context_builder: ContextBuilder,
) -> None:
    """Test that invalid session_id raises InvalidDataError."""
    session_id = -1
    mode = MemoryMode.LONG_TERM

    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await context_builder.build_context(session_id, mode)


@pytest.mark.asyncio
async def test_zero_session_id_raises_error(
    context_builder: ContextBuilder,
) -> None:
    """Test that zero session_id raises InvalidDataError."""
    session_id = 0
    mode = MemoryMode.SHORT_TERM

    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await context_builder.build_context(session_id, mode)
