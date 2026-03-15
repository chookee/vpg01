"""Message entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from ..enums import MemoryMode

# Validation constants
MAX_CONTENT_LENGTH: int = 10_000  # Maximum 10K characters per message


def _utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class Message:
    """Message entity representing dialog message.

    Attributes:
        message_id: Unique message identifier (non-negative integer).
            Zero (0) indicates a new message not yet persisted.
        session_id: Parent session identifier (positive integer).
        role: Message role (user or assistant).
        content: Message text content (non-empty, max 10K chars).
        timestamp: Message creation timestamp.
        model_used: Model name used for generation (assistant only).
        memory_mode_at_time: Memory mode at message creation time.

    Raises:
        ValueError: If message_id is negative, session_id not positive,
            content is empty, or content exceeds maximum length.
    """

    message_id: int
    session_id: int
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = field(default_factory=_utc_now)
    model_used: str | None = None
    memory_mode_at_time: MemoryMode | None = None

    VALID_ROLES: tuple[str, str] = ("user", "assistant")

    def __post_init__(self) -> None:
        """Validate message data after initialization."""
        if self.message_id < 0:
            raise ValueError(f"message_id must be non-negative, got {self.message_id}")
        if self.session_id <= 0:
            raise ValueError(f"session_id must be positive, got {self.session_id}")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty or whitespace-only")
        if self.role not in self.VALID_ROLES:
            raise ValueError(
                f"role must be 'user' or 'assistant', got '{self.role}'"
            )
        # Size validation to prevent DoS attacks
        if len(self.content) > MAX_CONTENT_LENGTH:
            raise ValueError(
                f"content length ({len(self.content)}) exceeds maximum allowed "
                f"({MAX_CONTENT_LENGTH} characters)"
            )
