"""Unit tests for DTOs validation."""

from datetime import datetime, timezone

import pytest

from src.application.dtos import MessageDTO, SessionDTO
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError


class TestMessageDTO:
    """Tests for MessageDTO validation."""

    def test_create_valid_message_dto(self) -> None:
        """Test creating valid MessageDTO."""
        timestamp = datetime.now(timezone.utc)
        dto = MessageDTO(
            message_id=1,
            session_id=2,
            role="user",
            content="Hello",
            timestamp=timestamp,
        )
        assert dto.message_id == 1
        assert dto.session_id == 2
        assert dto.role == "user"
        assert dto.content == "Hello"

    def test_create_with_optional_fields(self) -> None:
        """Test creating MessageDTO with optional fields."""
        timestamp = datetime.now(timezone.utc)
        dto = MessageDTO(
            message_id=1,
            session_id=2,
            role="assistant",
            content="Response",
            timestamp=timestamp,
            model_used="gpt-4",
            memory_mode_at_time=MemoryMode.LONG_TERM,
        )
        assert dto.model_used == "gpt-4"
        assert dto.memory_mode_at_time == MemoryMode.LONG_TERM

    def test_invalid_message_id_zero(self) -> None:
        """Test that zero message_id raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            MessageDTO(
                message_id=0,
                session_id=1,
                role="user",
                content="Hello",
                timestamp=timestamp,
            )

    def test_invalid_message_id_negative(self) -> None:
        """Test that negative message_id raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="message_id must be positive"):
            MessageDTO(
                message_id=-1,
                session_id=1,
                role="user",
                content="Hello",
                timestamp=timestamp,
            )

    def test_invalid_session_id_zero(self) -> None:
        """Test that zero session_id raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            MessageDTO(
                message_id=1,
                session_id=0,
                role="user",
                content="Hello",
                timestamp=timestamp,
            )

    def test_invalid_session_id_negative(self) -> None:
        """Test that negative session_id raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            MessageDTO(
                message_id=1,
                session_id=-1,
                role="user",
                content="Hello",
                timestamp=timestamp,
            )

    def test_invalid_role(self) -> None:
        """Test that invalid role raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="role must be"):
            MessageDTO(
                message_id=1,
                session_id=1,
                role="system",  # type: ignore[arg-type]
                content="Hello",
                timestamp=timestamp,
            )

    def test_empty_content(self) -> None:
        """Test that empty content raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="content cannot be empty"):
            MessageDTO(
                message_id=1,
                session_id=1,
                role="user",
                content="",
                timestamp=timestamp,
            )

    def test_whitespace_content(self) -> None:
        """Test that whitespace-only content raises InvalidDataError."""
        timestamp = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="content cannot be empty"):
            MessageDTO(
                message_id=1,
                session_id=1,
                role="user",
                content="   ",
                timestamp=timestamp,
            )

    def test_to_dict(self) -> None:
        """Test converting MessageDTO to dictionary."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dto = MessageDTO(
            message_id=1,
            session_id=2,
            role="user",
            content="Hello",
            timestamp=timestamp,
            model_used="gpt-4",
            memory_mode_at_time=MemoryMode.SHORT_TERM,
        )
        result = dto.to_dict()
        assert result == {
            "message_id": 1,
            "session_id": 2,
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T12:00:00+00:00",
            "model_used": "gpt-4",
            "memory_mode_at_time": "short_term",
        }

    def test_from_dict_valid(self) -> None:
        """Test creating MessageDTO from valid dictionary."""
        data = {
            "message_id": 1,
            "session_id": 2,
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T12:00:00+00:00",
            "model_used": "gpt-4",
            "memory_mode_at_time": "short_term",
        }
        dto = MessageDTO.from_dict(data)
        assert dto.message_id == 1
        assert dto.session_id == 2
        assert dto.role == "user"
        assert dto.content == "Hello"
        assert dto.model_used == "gpt-4"
        assert dto.memory_mode_at_time == MemoryMode.SHORT_TERM

    def test_from_dict_missing_required_field(self) -> None:
        """Test that missing required field raises InvalidDataError."""
        data = {
            "message_id": 1,
            "session_id": 2,
            "role": "user",
            "content": "Hello",
            # timestamp missing
        }
        with pytest.raises(InvalidDataError, match="Missing required field: timestamp"):
            MessageDTO.from_dict(data)

    def test_from_dict_invalid_timestamp(self) -> None:
        """Test that invalid timestamp format raises ValueError."""
        data = {
            "message_id": 1,
            "session_id": 2,
            "role": "user",
            "content": "Hello",
            "timestamp": "invalid-date",
        }
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            MessageDTO.from_dict(data)

    def test_from_dict_invalid_memory_mode(self) -> None:
        """Test that invalid memory_mode raises InvalidDataError."""
        data = {
            "message_id": 1,
            "session_id": 2,
            "role": "user",
            "content": "Hello",
            "timestamp": "2024-01-01T12:00:00+00:00",
            "memory_mode_at_time": "invalid_mode",
        }
        with pytest.raises(InvalidDataError, match="Invalid memory_mode"):
            MessageDTO.from_dict(data)


class TestSessionDTO:
    """Tests for SessionDTO validation."""

    def test_create_valid_session_dto(self) -> None:
        """Test creating valid SessionDTO."""
        now = datetime.now(timezone.utc)
        dto = SessionDTO(
            session_id=1,
            user_id=2,
            memory_mode=MemoryMode.LONG_TERM,
            created_at=now,
            last_activity=now,
        )
        assert dto.session_id == 1
        assert dto.user_id == 2
        assert dto.memory_mode == MemoryMode.LONG_TERM

    def test_invalid_session_id_zero(self) -> None:
        """Test that zero session_id raises InvalidDataError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            SessionDTO(
                session_id=0,
                user_id=1,
                memory_mode=MemoryMode.SHORT_TERM,
                created_at=now,
                last_activity=now,
            )

    def test_invalid_session_id_negative(self) -> None:
        """Test that negative session_id raises InvalidDataError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="session_id must be positive"):
            SessionDTO(
                session_id=-1,
                user_id=1,
                memory_mode=MemoryMode.SHORT_TERM,
                created_at=now,
                last_activity=now,
            )

    def test_invalid_user_id_zero(self) -> None:
        """Test that zero user_id raises InvalidDataError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="user_id must be positive"):
            SessionDTO(
                session_id=1,
                user_id=0,
                memory_mode=MemoryMode.SHORT_TERM,
                created_at=now,
                last_activity=now,
            )

    def test_invalid_user_id_negative(self) -> None:
        """Test that negative user_id raises InvalidDataError."""
        now = datetime.now(timezone.utc)
        with pytest.raises(InvalidDataError, match="user_id must be positive"):
            SessionDTO(
                session_id=1,
                user_id=-1,
                memory_mode=MemoryMode.SHORT_TERM,
                created_at=now,
                last_activity=now,
            )

    def test_to_dict(self) -> None:
        """Test converting SessionDTO to dictionary."""
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dto = SessionDTO(
            session_id=1,
            user_id=2,
            memory_mode=MemoryMode.BOTH,
            created_at=now,
            last_activity=now,
        )
        result = dto.to_dict()
        assert result == {
            "session_id": 1,
            "user_id": 2,
            "memory_mode": "both",
            "created_at": "2024-01-01T12:00:00+00:00",
            "last_activity": "2024-01-01T12:00:00+00:00",
        }

    def test_from_dict_valid(self) -> None:
        """Test creating SessionDTO from valid dictionary."""
        data = {
            "session_id": 1,
            "user_id": 2,
            "memory_mode": "long_term",
            "created_at": "2024-01-01T12:00:00+00:00",
            "last_activity": "2024-01-01T12:05:00+00:00",
        }
        dto = SessionDTO.from_dict(data)
        assert dto.session_id == 1
        assert dto.user_id == 2
        assert dto.memory_mode == MemoryMode.LONG_TERM

    def test_from_dict_missing_required_field(self) -> None:
        """Test that missing required field raises InvalidDataError."""
        data = {
            "session_id": 1,
            "user_id": 2,
            "memory_mode": "long_term",
            "created_at": "2024-01-01T12:00:00+00:00",
            # last_activity missing
        }
        with pytest.raises(InvalidDataError, match="Missing required field: last_activity"):
            SessionDTO.from_dict(data)

    def test_from_dict_invalid_timestamp(self) -> None:
        """Test that invalid timestamp format raises ValueError."""
        data = {
            "session_id": 1,
            "user_id": 2,
            "memory_mode": "long_term",
            "created_at": "invalid-date",
            "last_activity": "2024-01-01T12:05:00+00:00",
        }
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            SessionDTO.from_dict(data)

    def test_from_dict_invalid_memory_mode(self) -> None:
        """Test that invalid memory_mode raises InvalidDataError."""
        data = {
            "session_id": 1,
            "user_id": 2,
            "memory_mode": "invalid_mode",
            "created_at": "2024-01-01T12:00:00+00:00",
            "last_activity": "2024-01-01T12:05:00+00:00",
        }
        with pytest.raises(InvalidDataError, match="Invalid memory_mode"):
            SessionDTO.from_dict(data)
