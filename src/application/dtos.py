"""Data Transfer Objects for application layer.

This module provides DTOs for transferring data between application layers.
DTOs include validation logic to ensure data integrity and provide
serialization/deserialization methods for external communication.

Classes:
    MessageDTO: Data transfer object for Message entity.
    SessionDTO: Data transfer object for Session entity.

Example:
    >>> dto = MessageDTO(message_id=1, session_id=2, role="user",
    ...                  content="Hello", timestamp=datetime.now())
    >>> data = dto.to_dict()  # Serialize to dictionary
    >>> restored = MessageDTO.from_dict(data)  # Deserialize from dictionary
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError


@dataclass
class MessageDTO:
    """Data Transfer Object for Message entity.

    Used for transferring message data between application layers.
    Contains all message fields without business logic.

    Attributes:
        message_id: Unique message identifier.
        session_id: Parent session identifier.
        role: Message role (user or assistant).
        content: Message text content.
        timestamp: Message creation timestamp.
        model_used: Model name used for generation (optional).
        memory_mode_at_time: Memory mode at message creation (optional).
    """

    message_id: int
    session_id: int
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime
    model_used: Optional[str] = None
    memory_mode_at_time: Optional[MemoryMode] = None

    def __post_init__(self) -> None:
        """Validate DTO data after initialization."""
        if self.message_id <= 0:
            raise InvalidDataError(
                f"message_id must be positive, got {self.message_id}"
            )
        if self.session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {self.session_id}"
            )
        if self.role not in ("user", "assistant"):
            raise InvalidDataError(
                f"role must be 'user' or 'assistant', got '{self.role}'"
            )
        if not self.content or not self.content.strip():
            raise InvalidDataError("content cannot be empty or whitespace-only")

    def to_dict(self) -> dict:
        """Convert DTO to dictionary.

        Returns:
            Dictionary representation of the message.
        """
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "model_used": self.model_used,
            "memory_mode_at_time": (
                self.memory_mode_at_time.value
                if self.memory_mode_at_time
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MessageDTO":
        """Create DTO from dictionary.

        Args:
            data: Dictionary with message data.

        Returns:
            MessageDTO instance.

        Raises:
            InvalidDataError: If required fields are missing or invalid.
            ValueError: If timestamp format is invalid.
        """
        required_fields = ["message_id", "session_id", "role", "content", "timestamp"]
        for field_name in required_fields:
            if field_name not in data:
                raise InvalidDataError(f"Missing required field: {field_name}")

        try:
            timestamp = datetime.fromisoformat(data["timestamp"])
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid timestamp format: {data['timestamp']}. "
                f"Expected ISO 8601 format."
            ) from e

        memory_mode: Optional[MemoryMode] = None
        if data.get("memory_mode_at_time"):
            try:
                memory_mode = MemoryMode(data["memory_mode_at_time"])
            except ValueError as e:
                raise InvalidDataError(
                    f"Invalid memory_mode: {data['memory_mode_at_time']}. "
                    f"Valid values: {[m.value for m in MemoryMode]}"
                ) from e

        return cls(
            message_id=data["message_id"],
            session_id=data["session_id"],
            role=data["role"],
            content=data["content"],
            timestamp=timestamp,
            model_used=data.get("model_used"),
            memory_mode_at_time=memory_mode,
        )


@dataclass
class SessionDTO:
    """Data Transfer Object for Session entity.

    Used for transferring session data between application layers.
    Contains all session fields without business logic.

    Attributes:
        session_id: Unique session identifier.
        user_id: Owner user identifier.
        memory_mode: Current session memory mode.
        created_at: Session creation timestamp.
        last_activity: Last activity timestamp.
    """

    session_id: int
    user_id: int
    memory_mode: MemoryMode
    created_at: datetime
    last_activity: datetime

    def __post_init__(self) -> None:
        """Validate DTO data after initialization."""
        if self.session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {self.session_id}"
            )
        if self.user_id <= 0:
            raise InvalidDataError(
                f"user_id must be positive, got {self.user_id}"
            )

    def to_dict(self) -> dict:
        """Convert DTO to dictionary.

        Returns:
            Dictionary representation of the session.
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "memory_mode": self.memory_mode.value,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionDTO":
        """Create DTO from dictionary.

        Args:
            data: Dictionary with session data.

        Returns:
            SessionDTO instance.

        Raises:
            InvalidDataError: If required fields are missing or invalid.
            ValueError: If timestamp format is invalid.
        """
        required_fields = ["session_id", "user_id", "memory_mode", "created_at", "last_activity"]
        for field_name in required_fields:
            if field_name not in data:
                raise InvalidDataError(f"Missing required field: {field_name}")

        try:
            created_at = datetime.fromisoformat(data["created_at"])
            last_activity = datetime.fromisoformat(data["last_activity"])
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid timestamp format. Expected ISO 8601 format."
            ) from e

        try:
            memory_mode = MemoryMode(data["memory_mode"])
        except ValueError as e:
            raise InvalidDataError(
                f"Invalid memory_mode: {data['memory_mode']}. "
                f"Valid values: {[m.value for m in MemoryMode]}"
            ) from e

        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            memory_mode=memory_mode,
            created_at=created_at,
            last_activity=last_activity,
        )
