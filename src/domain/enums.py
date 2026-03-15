"""Domain enumerations."""

from enum import Enum


class MemoryMode(str, Enum):
    """Memory mode for session context management."""

    NO_MEMORY = "no_memory"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    BOTH = "both"
