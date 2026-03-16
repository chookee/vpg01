"""User entity."""

from dataclasses import dataclass, field
from typing import Optional

from ..enums import MemoryMode


@dataclass
class User:
    """User entity representing application user.

    Attributes:
        user_id: Unique user identifier (positive integer).
            Can be None for new entities not yet persisted.
        telegram_id: Telegram user identifier (optional, positive).
        default_mode: Default memory mode for new sessions.

    Raises:
        ValueError: If user_id is set and not positive, or telegram_id is not positive.
    """

    user_id: Optional[int] = None
    telegram_id: int | None = None
    default_mode: MemoryMode = field(default=MemoryMode.SHORT_TERM)

    def __post_init__(self) -> None:
        """Validate user data after initialization."""
        # user_id can be None for new entities, but if set must be positive
        if self.user_id is not None and self.user_id <= 0:
            raise ValueError(f"user_id must be positive, got {self.user_id}")
        if self.telegram_id is not None and self.telegram_id <= 0:
            raise ValueError(f"telegram_id must be positive, got {self.telegram_id}")

    @property
    def is_persisted(self) -> bool:
        """Check if user has been persisted (has a user_id)."""
        return self.user_id is not None
