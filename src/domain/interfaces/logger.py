"""Logger port."""

from abc import ABC, abstractmethod
from typing import Any


class Logger(ABC):
    """Abstract base class for logger."""

    @abstractmethod
    def info(self, message: str, *args: object, **kwargs: Any) -> None:
        """Log an info message.

        Args:
            message: Log message with optional format placeholders.
            *args: Arguments for message formatting.
            **kwargs: Additional keyword arguments.
        """
        raise NotImplementedError

    @abstractmethod
    def debug(self, message: str, *args: object, **kwargs: Any) -> None:
        """Log a debug message.

        Args:
            message: Log message with optional format placeholders.
            *args: Arguments for message formatting.
            **kwargs: Additional keyword arguments.
        """
        raise NotImplementedError

    @abstractmethod
    def error(self, message: str, *args: object, **kwargs: Any) -> None:
        """Log an error message.

        Args:
            message: Log message with optional format placeholders.
            *args: Arguments for message formatting.
            **kwargs: Additional keyword arguments.
        """
        raise NotImplementedError

    @abstractmethod
    def warning(self, message: str, *args: object, **kwargs: Any) -> None:
        """Log a warning message.

        Args:
            message: Log message with optional format placeholders.
            *args: Arguments for message formatting.
            **kwargs: Additional keyword arguments.
        """
        raise NotImplementedError
