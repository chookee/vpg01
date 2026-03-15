"""In-memory session store for short-term memory."""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque, Dict, Final, List, Optional

from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError


@dataclass
class SessionData:
    """Container for session and its messages in memory."""

    session: Session
    messages: Deque[Message] = field(default_factory=deque)
    max_messages: int = 50


class InMemorySessionStore:
    """In-memory storage for active sessions and their messages.

    Uses asyncio.Lock for thread-safe operations in async context.
    Supports automatic cleanup of inactive sessions by TTL.
    """

    DEFAULT_TTL_SECONDS: Final[int] = 3600
    DEFAULT_MAX_MESSAGES: Final[int] = 50

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> None:
        """Initialize the in-memory session store.

        Args:
            ttl_seconds: Time-to-live for inactive sessions in seconds.
            max_messages: Maximum messages to keep per session in memory.
        """
        self._sessions: Dict[int, SessionData] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._ttl_seconds: int = ttl_seconds
        self._max_messages: int = max_messages
        self._current_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_lock(self) -> asyncio.Lock:
        """Get or create lock for current event loop.
        
        Lazy initialization ensures lock is bound to correct event loop.
        """
        current_loop = asyncio.get_event_loop()
        if self._lock is None or self._current_loop is not current_loop:
            self._lock = asyncio.Lock()
            self._current_loop = current_loop
        return self._lock

    async def _validate_session_id(self, session_id: int) -> None:
        """Validate session ID is positive."""
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )

    async def add_message(
        self,
        session_id: int,
        message: Message,
        session: Optional[Session] = None,
    ) -> None:
        """Add a message to the session's in-memory store.

        Creates a new session entry if it doesn't exist.

        Args:
            session_id: The session identifier.
            message: The message to store.
            session: Optional session object. If provided and session
                doesn't exist, it will be created.

        Raises:
            InvalidDataError: If session_id is not positive or message is None.
        """
        await self._validate_session_id(session_id)
        if message is None:
            raise InvalidDataError("message cannot be None")

        lock = self._get_lock()
        async with lock:
            if session_id not in self._sessions:
                if session is None:
                    session = Session(
                        session_id=session_id,
                        user_id=1,
                        memory_mode=MemoryMode.SHORT_TERM,
                        created_at=datetime.now(),
                        last_activity=datetime.now(),
                    )
                self._sessions[session_id] = SessionData(
                    session=session,
                    max_messages=self._max_messages,
                )

            session_data = self._sessions[session_id]
            session_data.messages.append(message)

            while len(session_data.messages) > session_data.max_messages:
                session_data.messages.popleft()

            session_data.session.last_activity = datetime.now()

    async def get_messages(self, session_id: int) -> List[Message]:
        """Get all messages for a session from memory.

        Args:
            session_id: The session identifier.

        Returns:
            List of messages in chronological order.
            Empty list if session doesn't exist.
        """
        await self._validate_session_id(session_id)

        lock = self._get_lock()
        async with lock:
            if session_id not in self._sessions:
                return []
            return list(self._sessions[session_id].messages)

    async def clear_session(self, session_id: int) -> bool:
        """Remove a session and all its messages from memory.

        Args:
            session_id: The session identifier.

        Returns:
            True if session was removed, False if it didn't exist.
        """
        await self._validate_session_id(session_id)

        lock = self._get_lock()
        async with lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def get_session(self, session_id: int) -> Optional[Session]:
        """Get session object by ID.

        Args:
            session_id: The session identifier.

        Returns:
            Session object or None if not found.
        """
        await self._validate_session_id(session_id)

        lock = self._get_lock()
        async with lock:
            if session_id in self._sessions:
                return self._sessions[session_id].session
            return None

    async def cleanup_inactive(self) -> int:
        """Remove sessions that have been inactive longer than TTL.

        Returns:
            Number of sessions removed.
        """
        lock = self._get_lock()
        async with lock:
            now = datetime.now()
            to_remove = []

            for sid, session_data in self._sessions.items():
                try:
                    elapsed = (
                        now - session_data.session.last_activity
                    ).total_seconds()
                    if elapsed > self._ttl_seconds:
                        to_remove.append(sid)
                except (AttributeError, TypeError):
                    to_remove.append(sid)

            for sid in to_remove:
                del self._sessions[sid]

            return len(to_remove)

    async def get_active_session_ids(self) -> List[int]:
        """Get list of all active session IDs.

        Returns:
            List of session IDs currently in memory.
        """
        lock = self._get_lock()
        async with lock:
            return list(self._sessions.keys())

    async def get_size(self) -> int:
        """Return number of active sessions.

        Returns:
            Number of sessions in store.
        """
        lock = self._get_lock()
        async with lock:
            return len(self._sessions)
