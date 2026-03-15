"""Repository ports for data persistence."""

from abc import abstractmethod
from typing import Protocol, runtime_checkable

from ..entities.message import Message
from ..entities.session import Session
from ..entities.user import User
from ..enums import MemoryMode


@runtime_checkable
class MessageRepository(Protocol):
    """Protocol for message repository."""

    @abstractmethod
    async def add(self, message: Message) -> int:
        """Add a message to the repository.

        Args:
            message: Message entity to add.

        Returns:
            Assigned message_id for the inserted message.
        """
        pass

    @abstractmethod
    async def get_by_session(self, session_id: int) -> list[Message]:
        """Get all messages for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages ordered by timestamp.
        """
        pass

    @abstractmethod
    async def get_by_id(self, message_id: int) -> Message | None:
        """Get a message by ID.

        Args:
            message_id: Message identifier.

        Returns:
            Message entity or None if not found.
        """
        pass

    @abstractmethod
    async def update(self, message: Message) -> None:
        """Update an existing message.

        Args:
            message: Message entity with updated data.
        """
        pass

    @abstractmethod
    async def delete(self, message_id: int) -> None:
        """Delete a message by ID.

        Args:
            message_id: Message identifier to delete.
        """
        pass

    @abstractmethod
    async def delete_by_session(self, session_id: int) -> None:
        """Delete all messages for a session.

        Args:
            session_id: Session identifier.
        """
        pass

    @abstractmethod
    async def get_by_sessions_batch(self, session_ids: list[int]) -> list[Message]:
        """Get messages for multiple sessions efficiently.

        Solves N+1 query problem by fetching all messages in a single database round-trip.

        Args:
            session_ids: List of session identifiers.

        Returns:
            List of messages ordered by session_id and timestamp.
        """
        pass


@runtime_checkable
class SessionRepository(Protocol):
    """Protocol for session repository."""

    @abstractmethod
    async def create(self, session: Session) -> None:
        """Create a new session.

        Args:
            session: Session entity to create.
        """
        pass

    @abstractmethod
    async def get(self, session_id: int) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session entity or None if not found.
        """
        pass

    @abstractmethod
    async def update_mode(self, session_id: int, memory_mode: MemoryMode) -> None:
        """Update session memory mode.

        Args:
            session_id: Session identifier.
            memory_mode: New memory mode.
        """
        pass

    @abstractmethod
    async def delete(self, session_id: int) -> None:
        """Delete a session by ID.

        Args:
            session_id: Session identifier to delete.
        """
        pass


@runtime_checkable
class UserRepository(Protocol):
    """Protocol for user repository."""

    @abstractmethod
    async def create(self, user: User) -> None:
        """Create a new user.

        Args:
            user: User entity to create.
        """
        pass

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None:
        """Get a user by ID.

        Args:
            user_id: User identifier.

        Returns:
            User entity or None if not found.
        """
        pass

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get a user by Telegram ID.

        Args:
            telegram_id: Telegram identifier.

        Returns:
            User entity or None if not found.
        """
        pass

    @abstractmethod
    async def update(self, user: User) -> None:
        """Update an existing user.

        Args:
            user: User entity with updated data.
        """
        pass


@runtime_checkable
class SessionStore(Protocol):
    """Protocol for short-term in-memory session store.

    This is a port for volatile, in-memory storage of active
    session messages. Implementations should be fast and may
    include automatic cleanup of inactive sessions.
    """

    @abstractmethod
    async def add_message(
        self,
        session_id: int,
        message: Message,
        session: Session | None = None,
    ) -> None:
        """Add a message to the session's in-memory store.

        Args:
            session_id: The session identifier.
            message: The message to store.
            session: Optional session object for creation.
        """
        pass

    @abstractmethod
    async def get_messages(self, session_id: int) -> list[Message]:
        """Get all messages for a session from memory.

        Args:
            session_id: The session identifier.

        Returns:
            List of messages in chronological order.
        """
        pass

    @abstractmethod
    async def clear_session(self, session_id: int) -> bool:
        """Remove a session and all its messages from memory.

        Args:
            session_id: The session identifier.

        Returns:
            True if session was removed, False otherwise.
        """
        pass

    @abstractmethod
    async def get_session(self, session_id: int) -> Session | None:
        """Get session object by ID.

        Args:
            session_id: The session identifier.

        Returns:
            Session object or None if not found.
        """
        pass

    @abstractmethod
    async def update_message(self, message: Message) -> bool:
        """Update a message in the session's in-memory store.

        Args:
            message: Message entity with updated content.

        Returns:
            True if message was updated, False if not found.
        """
        pass

    @abstractmethod
    async def delete_message(self, message_id: int, session_id: int) -> bool:
        """Delete a message from the session's in-memory store.

        Args:
            message_id: Message identifier to delete.
            session_id: Session identifier.

        Returns:
            True if message was deleted, False if not found.
        """
        pass
