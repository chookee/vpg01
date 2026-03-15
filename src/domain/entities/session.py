"""Session entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..enums import MemoryMode


def _utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass
class Session:
    """Session entity representing user dialog session.

    Attributes:
        session_id: Unique session identifier (positive integer).
        user_id: Owner user identifier (positive integer).
        memory_mode: Current session memory mode.
        created_at: Session creation timestamp.
        last_activity: Last activity timestamp.

    Raises:
        ValueError: If session_id or user_id is not positive.
    """

    session_id: int
    user_id: int
    memory_mode: MemoryMode = field(default=MemoryMode.SHORT_TERM)
    created_at: datetime = field(default_factory=_utc_now)
    last_activity: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate session data after initialization."""
        if self.session_id <= 0:
            raise ValueError(f"session_id must be positive, got {self.session_id}")
        if self.user_id <= 0:
            raise ValueError(f"user_id must be positive, got {self.user_id}")
