"""Session entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from ..enums import MemoryMode


def _utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class Session:
    """Session entity representing user dialog session.

    Attributes:
        session_id: Unique session identifier (positive integer).
            Can be None for new entities not yet persisted.
        user_id: Owner user identifier (positive integer).
            Can be None for new entities not yet persisted.
        memory_mode: Current session memory mode.
        created_at: Session creation timestamp.
        last_activity: Last activity timestamp.

    Raises:
        ValueError: If session_id or user_id is set and not positive.
    """

    session_id: Optional[int] = None
    user_id: Optional[int] = None
    memory_mode: MemoryMode = field(default=MemoryMode.SHORT_TERM)
    created_at: datetime = field(default_factory=_utc_now)
    last_activity: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate session data after initialization."""
        # session_id and user_id can be None for new entities, but if set must be positive
        if self.session_id is not None and self.session_id <= 0:
            raise ValueError(f"session_id must be positive, got {self.session_id}")
        if self.user_id is not None and self.user_id <= 0:
            raise ValueError(f"user_id must be positive, got {self.user_id}")

    @property
    def is_persisted(self) -> bool:
        """Check if session has been persisted (has a session_id)."""
        return self.session_id is not None
