"""Domain-specific exceptions."""


class DomainError(Exception):
    """Base exception for domain errors."""


class InvalidDataError(DomainError):
    """Raised when invalid data is provided."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class MessageNotFoundError(DomainError):
    """Raised when a message is not found."""

    def __init__(self, message_id: int) -> None:
        self.message_id = message_id
        super().__init__(f"Message with id={message_id} not found")


class SessionNotFoundError(DomainError):
    """Raised when a session is not found."""

    def __init__(self, session_id: int) -> None:
        self.session_id = session_id
        super().__init__(f"Session with id={session_id} not found")


class UserNotFoundError(DomainError):
    """Raised when a user is not found."""

    def __init__(
        self, user_id: int | None = None, telegram_id: int | None = None
    ) -> None:
        if user_id is not None:
            super().__init__(f"User with id={user_id} not found")
        elif telegram_id is not None:
            super().__init__(f"User with telegram_id={telegram_id} not found")
        else:
            super().__init__("User not found")
