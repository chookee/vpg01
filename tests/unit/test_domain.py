"""Domain entities tests."""

from datetime import datetime, timezone

import pytest

from src.domain.entities.message import MAX_CONTENT_LENGTH, Message
from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.exceptions import (
    DomainError,
    MessageNotFoundError,
    SessionNotFoundError,
    UserNotFoundError,
)


class TestDomainExceptions:
    """Domain exceptions tests."""

    def test_domain_error_is_exception(self) -> None:
        """DomainError should be an Exception."""
        assert issubclass(DomainError, Exception)

    def test_message_not_found_error(self) -> None:
        """MessageNotFoundError should contain message_id."""
        error = MessageNotFoundError(42)
        assert error.message_id == 42
        assert "42" in str(error)

    def test_session_not_found_error(self) -> None:
        """SessionNotFoundError should contain session_id."""
        error = SessionNotFoundError(99)
        assert error.session_id == 99
        assert "99" in str(error)

    def test_user_not_found_error_by_user_id(self) -> None:
        """UserNotFoundError should work with user_id."""
        error = UserNotFoundError(user_id=123)
        assert "123" in str(error)

    def test_user_not_found_error_by_telegram_id(self) -> None:
        """UserNotFoundError should work with telegram_id."""
        error = UserNotFoundError(telegram_id=456)
        assert "456" in str(error)

    def test_user_not_found_error_no_id(self) -> None:
        """UserNotFoundError should work without IDs."""
        error = UserNotFoundError()
        assert "User not found" in str(error)


class TestUser:
    """User entity tests."""

    def test_create_user_minimal(self) -> None:
        """Test creating user with minimal required fields."""
        user = User(user_id=1)

        assert user.user_id == 1
        assert user.telegram_id is None
        assert user.default_mode == MemoryMode.SHORT_TERM

    def test_create_user_full(self) -> None:
        """Test creating user with all fields."""
        user = User(
            user_id=42,
            telegram_id=123456789,
            default_mode=MemoryMode.LONG_TERM,
        )

        assert user.user_id == 42
        assert user.telegram_id == 123456789
        assert user.default_mode == MemoryMode.LONG_TERM

    def test_create_user_invalid_id_zero(self) -> None:
        """Test that user_id=0 raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be positive"):
            User(user_id=0)

    def test_create_user_invalid_id_negative(self) -> None:
        """Test that negative user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be positive"):
            User(user_id=-1)

    def test_create_user_invalid_telegram_id(self) -> None:
        """Test that negative telegram_id raises ValueError."""
        with pytest.raises(ValueError, match="telegram_id must be positive"):
            User(user_id=1, telegram_id=-100)

    def test_create_user_invalid_telegram_id_zero(self) -> None:
        """Test that telegram_id=0 raises ValueError."""
        with pytest.raises(ValueError, match="telegram_id must be positive"):
            User(user_id=1, telegram_id=0)


class TestSession:
    """Session entity tests."""

    def test_create_session_minimal(self) -> None:
        """Test creating session with minimal required fields."""
        session = Session(session_id=1, user_id=42)

        assert session.session_id == 1
        assert session.user_id == 42
        assert session.memory_mode == MemoryMode.SHORT_TERM
        assert session.created_at is not None
        assert session.last_activity is not None

    def test_create_session_full(self) -> None:
        """Test creating session with all fields."""
        created_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        session = Session(
            session_id=100,
            user_id=42,
            memory_mode=MemoryMode.BOTH,
            created_at=created_at,
            last_activity=created_at,
        )

        assert session.session_id == 100
        assert session.user_id == 42
        assert session.memory_mode == MemoryMode.BOTH
        assert session.created_at == created_at
        assert session.last_activity == created_at

    def test_create_session_invalid_session_id(self) -> None:
        """Test that invalid session_id raises ValueError."""
        with pytest.raises(ValueError, match="session_id must be positive"):
            Session(session_id=0, user_id=42)

    def test_create_session_invalid_user_id(self) -> None:
        """Test that invalid user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be positive"):
            Session(session_id=1, user_id=-5)


class TestMessage:
    """Message entity tests."""

    def test_create_user_message(self) -> None:
        """Test creating user message."""
        msg = Message(
            message_id=1,
            session_id=10,
            role="user",
            content="Hello!",
        )

        assert msg.message_id == 1
        assert msg.session_id == 10
        assert msg.role == "user"
        assert msg.content == "Hello!"
        assert msg.model_used is None
        assert msg.memory_mode_at_time is None

    def test_create_assistant_message(self) -> None:
        """Test creating assistant message with metadata."""
        msg = Message(
            message_id=2,
            session_id=10,
            role="assistant",
            content="Hi there!",
            model_used="llama3",
            memory_mode_at_time=MemoryMode.LONG_TERM,
        )

        assert msg.message_id == 2
        assert msg.session_id == 10
        assert msg.role == "assistant"
        assert msg.content == "Hi there!"
        assert msg.model_used == "llama3"
        assert msg.memory_mode_at_time == MemoryMode.LONG_TERM

    def test_create_message_invalid_message_id(self) -> None:
        """Test that invalid message_id raises ValueError."""
        with pytest.raises(ValueError, match="message_id must be positive"):
            Message(message_id=0, session_id=1, role="user", content="Test")

    def test_create_message_invalid_session_id(self) -> None:
        """Test that invalid session_id raises ValueError."""
        with pytest.raises(ValueError, match="session_id must be positive"):
            Message(message_id=1, session_id=-1, role="user", content="Test")

    def test_create_message_empty_content(self) -> None:
        """Test that empty content raises ValueError."""
        with pytest.raises(ValueError, match="content cannot be empty"):
            Message(message_id=1, session_id=1, role="user", content="")

    def test_create_message_whitespace_content(self) -> None:
        """Test that whitespace-only content raises ValueError."""
        with pytest.raises(ValueError, match="content cannot be empty or whitespace-only"):
            Message(message_id=1, session_id=1, role="user", content="   ")

    def test_create_message_newline_content(self) -> None:
        """Test that newline-only content raises ValueError."""
        with pytest.raises(ValueError, match="content cannot be empty or whitespace-only"):
            Message(message_id=1, session_id=1, role="user", content="\n")

    def test_create_message_invalid_role(self) -> None:
        """Test that invalid role is rejected."""
        with pytest.raises(ValueError, match="role must be 'user' or 'assistant'"):
            Message(message_id=1, session_id=1, role="system", content="Test")

    def test_create_message_content_too_long(self) -> None:
        """Test that content exceeding MAX_CONTENT_LENGTH is rejected."""
        long_content = "x" * (MAX_CONTENT_LENGTH + 1)
        with pytest.raises(ValueError, match="content length.*exceeds maximum allowed"):
            Message(message_id=1, session_id=1, role="user", content=long_content)

    def test_create_message_content_at_limit(self) -> None:
        """Test that content at exactly MAX_CONTENT_LENGTH is accepted."""
        content = "x" * MAX_CONTENT_LENGTH
        msg = Message(message_id=1, session_id=1, role="user", content=content)
        assert len(msg.content) == MAX_CONTENT_LENGTH

    def test_max_content_length_constant(self) -> None:
        """Test MAX_CONTENT_LENGTH constant is defined."""
        assert MAX_CONTENT_LENGTH == 10_000
        assert isinstance(MAX_CONTENT_LENGTH, int)
        assert MAX_CONTENT_LENGTH > 0


class TestMemoryMode:
    """MemoryMode enumeration tests."""

    def test_memory_mode_values(self) -> None:
        """Test MemoryMode enum values."""
        assert MemoryMode.NO_MEMORY.value == "no_memory"
        assert MemoryMode.SHORT_TERM.value == "short_term"
        assert MemoryMode.LONG_TERM.value == "long_term"
        assert MemoryMode.BOTH.value == "both"

    def test_memory_mode_comparison(self) -> None:
        """Test MemoryMode string comparison."""
        assert MemoryMode.SHORT_TERM == "short_term"
        assert MemoryMode.LONG_TERM != MemoryMode.NO_MEMORY
