"""Tests for InMemorySessionStore."""

import asyncio
from datetime import datetime

import pytest

from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError
from src.infrastructure.repositories.inmemory_session_store import (
    InMemorySessionStore,
)


@pytest.fixture
def store() -> InMemorySessionStore:
    """Create an in-memory session store for testing."""
    return InMemorySessionStore(ttl_seconds=60, max_messages=10)


@pytest.fixture
def sample_session() -> Session:
    """Create a sample session for testing."""
    return Session(
        session_id=1,
        user_id=123,
        memory_mode=MemoryMode.SHORT_TERM,
        created_at=datetime.now(),
        last_activity=datetime.now(),
    )


@pytest.fixture
def sample_message() -> Message:
    """Create a sample message for testing."""
    return Message(
        message_id=1,
        session_id=1,
        role="user",
        content="Hello, World!",
        timestamp=datetime.now(),
        model_used="test-model",
        memory_mode_at_time=MemoryMode.SHORT_TERM,
    )


@pytest.mark.asyncio
async def test_add_message_creates_session(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test that adding a message creates a new session entry."""
    await store.add_message(session_id=1, message=sample_message)

    messages = await store.get_messages(1)
    assert len(messages) == 1
    assert messages[0].content == "Hello, World!"


@pytest.mark.asyncio
async def test_add_message_with_session_object(
    store: InMemorySessionStore,
    sample_message: Message,
    sample_session: Session,
) -> None:
    """Test adding a message with explicit session object."""
    await store.add_message(
        session_id=1,
        message=sample_message,
        session=sample_session,
    )

    stored_session = await store.get_session(1)
    assert stored_session is not None
    assert stored_session.user_id == 123
    assert stored_session.memory_mode == MemoryMode.SHORT_TERM


@pytest.mark.asyncio
async def test_get_messages_empty(store: InMemorySessionStore) -> None:
    """Test getting messages from non-existent session."""
    messages = await store.get_messages(999)
    assert messages == []


@pytest.mark.asyncio
async def test_add_multiple_messages(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test adding multiple messages to the same session."""
    for i in range(5):
        msg = Message(
            message_id=i + 1,
            session_id=1,
            role="user" if i % 2 == 0 else "assistant",
            content=f"Message {i}",
            timestamp=datetime.now(),
            model_used="test",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        )
        await store.add_message(session_id=1, message=msg)

    messages = await store.get_messages(1)
    assert len(messages) == 5
    assert messages[0].content == "Message 0"
    assert messages[4].content == "Message 4"


@pytest.mark.asyncio
async def test_message_limit_enforced(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test that message limit is enforced and old messages are trimmed."""
    for i in range(15):
        msg = Message(
            message_id=i + 1,
            session_id=1,
            role="user",
            content=f"Message {i}",
            timestamp=datetime.now(),
            model_used="test",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        )
        await store.add_message(session_id=1, message=msg)

    messages = await store.get_messages(1)
    assert len(messages) == 10
    assert messages[0].content == "Message 5"
    assert messages[9].content == "Message 14"


@pytest.mark.asyncio
async def test_clear_session(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test clearing a session."""
    await store.add_message(session_id=1, message=sample_message)

    result = await store.clear_session(1)
    assert result is True

    messages = await store.get_messages(1)
    assert messages == []


@pytest.mark.asyncio
async def test_clear_nonexistent_session(
    store: InMemorySessionStore,
) -> None:
    """Test clearing a non-existent session."""
    result = await store.clear_session(999)
    assert result is False


@pytest.mark.asyncio
async def test_get_session(
    store: InMemorySessionStore,
    sample_message: Message,
    sample_session: Session,
) -> None:
    """Test getting session by ID."""
    await store.add_message(
        session_id=1,
        message=sample_message,
        session=sample_session,
    )

    stored_session = await store.get_session(1)
    assert stored_session is not None
    assert stored_session.session_id == 1
    assert stored_session.user_id == 123


@pytest.mark.asyncio
async def test_get_nonexistent_session(
    store: InMemorySessionStore,
) -> None:
    """Test getting non-existent session."""
    session = await store.get_session(999)
    assert session is None


@pytest.mark.asyncio
async def test_cleanup_inactive(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test cleanup of inactive sessions."""
    store_with_short_ttl = InMemorySessionStore(ttl_seconds=1, max_messages=10)

    await store_with_short_ttl.add_message(session_id=1, message=sample_message)
    await asyncio.sleep(1.5)

    removed_count = await store_with_short_ttl.cleanup_inactive()
    assert removed_count == 1

    messages = await store_with_short_ttl.get_messages(1)
    assert messages == []


@pytest.mark.asyncio
async def test_cleanup_keeps_active_sessions(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test that cleanup keeps active sessions."""
    await store.add_message(session_id=1, message=sample_message)

    removed_count = await store.cleanup_inactive()
    assert removed_count == 0

    messages = await store.get_messages(1)
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_get_active_session_ids(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test getting list of active session IDs."""
    for session_id in [1, 2, 3]:
        msg = Message(
            message_id=session_id,
            session_id=session_id,
            role="user",
            content=f"Message {session_id}",
            timestamp=datetime.now(),
            model_used="test",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        )
        await store.add_message(session_id=session_id, message=msg)

    ids = await store.get_active_session_ids()
    assert sorted(ids) == [1, 2, 3]


@pytest.mark.asyncio
async def test_store_size(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test getting store size."""
    for session_id in [1, 2, 3]:
        await store.add_message(session_id=session_id, message=sample_message)

    size = await store.get_size()
    assert size == 3


@pytest.mark.asyncio
async def test_concurrent_access(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test thread-safe concurrent access."""

    async def add_messages(session_id: int) -> None:
        for i in range(5):
            msg = Message(
                message_id=session_id * 100 + i,
                session_id=session_id,
                role="user",
                content=f"Msg {i}",
                timestamp=datetime.now(),
                model_used="test",
                memory_mode_at_time=MemoryMode.SHORT_TERM,
            )
            await store.add_message(session_id=session_id, message=msg)

    tasks = [add_messages(i) for i in range(1, 6)]
    await asyncio.gather(*tasks)

    for session_id in range(1, 6):
        messages = await store.get_messages(session_id)
        assert len(messages) == 5


@pytest.mark.asyncio
async def test_add_message_invalid_session_id(
    store: InMemorySessionStore,
    sample_message: Message,
) -> None:
    """Test that negative session_id raises InvalidDataError."""
    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await store.add_message(session_id=-1, message=sample_message)

    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await store.add_message(session_id=0, message=sample_message)


@pytest.mark.asyncio
async def test_add_message_none_raises(
    store: InMemorySessionStore,
) -> None:
    """Test that None message raises InvalidDataError."""
    with pytest.raises(InvalidDataError, match="message cannot be None"):
        await store.add_message(session_id=1, message=None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_messages_invalid_session_id(
    store: InMemorySessionStore,
) -> None:
    """Test that negative session_id raises InvalidDataError."""
    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await store.get_messages(session_id=-1)


@pytest.mark.asyncio
async def test_clear_session_invalid_id(
    store: InMemorySessionStore,
) -> None:
    """Test that negative session_id raises InvalidDataError."""
    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await store.clear_session(session_id=0)


@pytest.mark.asyncio
async def test_get_session_invalid_id(
    store: InMemorySessionStore,
) -> None:
    """Test that negative session_id raises InvalidDataError."""
    with pytest.raises(InvalidDataError, match="session_id must be positive"):
        await store.get_session(session_id=-1)
