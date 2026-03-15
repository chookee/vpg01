"""Message entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from ..enums import MemoryMode


def _utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class Message:
    """Message entity representing dialog message.

    Attributes:
        message_id: Unique message identifier (positive integer).
        session_id: Parent session identifier (positive integer).
        role: Message role (user or assistant).
        content: Message text content (non-empty).
        timestamp: Message creation timestamp.
        model_used: Model name used for generation (assistant only).
        memory_mode_at_time: Memory mode at message creation time.

    Raises:
        ValueError: If message_id, session_id not positive or content is empty.
    """

    message_id: int
    session_id: int
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = field(default_factory=_utc_now)
    model_used: str | None = None
    memory_mode_at_time: MemoryMode | None = None

    def __post_init__(self) -> None:
        """Validate message data after initialization."""
        if self.message_id <= 0:
            raise ValueError(f"message_id must be positive, got {self.message_id}")
        if self.session_id <= 0:
            raise ValueError(f"session_id must be positive, got {self.session_id}")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty or whitespace-only")
