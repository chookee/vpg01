"""In-memory session store for short-term memory."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Final, List, Optional
import itertools

from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError
from src.domain.interfaces.repositories import SessionStore

logger = logging.getLogger(__name__)


@dataclass
class SessionData:
    """Container for session and its messages in memory."""

    session: Session
    messages: Deque[Message] = field(default_factory=deque)
    max_messages: int = 50


class InMemorySessionStore(SessionStore):
    """In-memory storage for active sessions and their messages.

    Uses asyncio.Lock for thread-safe operations in async context.
    Supports automatic cleanup of inactive sessions by TTL.
    """

    DEFAULT_TTL_SECONDS: Final[int] = 3600
    DEFAULT_MAX_MESSAGES: Final[int] = 50
    MAX_SESSIONS: Final[int] = 10_000
    DEFAULT_CLEANUP_INTERVAL: Final[int] = 300  # 5 minutes

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_messages: int = DEFAULT_MAX_MESSAGES,
        max_sessions: int = MAX_SESSIONS,
        cleanup_interval: int = DEFAULT_CLEANUP_INTERVAL,
    ) -> None:
        """Initialize the in-memory session store.

        Args:
            ttl_seconds: Time-to-live for inactive sessions in seconds.
            max_messages: Maximum messages to keep per session in memory.
            max_sessions: Maximum number of active sessions (DoS protection).
            cleanup_interval: Interval for background cleanup in seconds.
        """
        self._sessions: Dict[int, SessionData] = {}
        self._ttl_seconds: int = ttl_seconds
        self._max_messages: int = max_messages
        self._max_sessions: int = max_sessions
        self._cleanup_interval: int = cleanup_interval
        # Lazy lock — создаётся при первом использовании в async контексте
        # Это предотвращает привязку к неправильному event loop
        self._lock: asyncio.Lock | None = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
        # Counter for generating unique message IDs (starts from 1_000_000 to avoid collision with DB IDs)
        self._message_id_counter = itertools.count(1_000_000)

    def _get_lock(self) -> asyncio.Lock:
        """Get or create lock bound to current event loop.

        Returns:
            asyncio.Lock instance bound to current event loop.
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _validate_session_id(self, session_id: int) -> None:
        """Validate session ID is positive."""
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )

    async def _evict_oldest_session(self) -> None:
        """Evict session with oldest last_activity to free space.

        Called when max_sessions limit is reached.
        """
        if not self._sessions:
            return

        oldest_id = min(
            self._sessions.keys(),
            key=lambda sid: self._sessions[sid].session.last_activity,
        )
        del self._sessions[oldest_id]
        logger.warning(
            f"Evicted oldest session {oldest_id} due to max_sessions limit ({self._max_sessions})"
        )

    async def start_background_cleanup(self) -> None:
        """Start background task for periodic cleanup.

        This method should be called during application startup.
        """
        if self._cleanup_task is not None and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return

        self._shutdown_event.clear()
        self._cleanup_task = asyncio.create_task(
            self._cleanup_loop(),
            name="InMemorySessionStore-cleanup",
        )
        logger.info(f"Started background cleanup (interval={self._cleanup_interval}s)")

    async def _cleanup_loop(self) -> None:
        """Background loop for periodic cleanup.

        This loop runs until _shutdown_event is set.
        It wakes up every _cleanup_interval seconds to clean up inactive sessions.
        """
        try:
            while not self._shutdown_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._cleanup_interval,
                    )
                except asyncio.TimeoutError:
                    # Время вышло — выполняем cleanup
                    try:
                        removed = await self.cleanup_inactive()
                        if removed > 0:
                            logger.info(f"Cleaned up {removed} inactive sessions")
                    except Exception as e:
                        # Log error but continue running — don't crash the cleanup task
                        logger.error(f"Cleanup error: {type(e).__name__}: {e}")
        except asyncio.CancelledError:
            logger.info("Cleanup task cancelled")
            raise
        finally:
            # Ensure task reference is cleared
            self._cleanup_task = None
            logger.debug("Cleanup task reference cleared")

    async def stop_background_cleanup(self) -> None:
        """Stop background cleanup task.

        This method should be called during application shutdown.
        """
        if self._cleanup_task is None:
            return

        self._shutdown_event.set()
        try:
            self._cleanup_task.cancel()
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup_task = None
            logger.info("Background cleanup stopped")

    async def add_message(
        self,
        session_id: int,
        message: Message,
        session: Optional[Session] = None,
        user_id: Optional[int] = None,
    ) -> int:
        """Add a message to the session's in-memory store.

        Creates a new session entry if it doesn't exist.
        Assigns a unique message ID from internal counter.

        Args:
            session_id: The session identifier.
            message: The message to store.
            session: Optional session object. If provided and session
                doesn't exist, it will be created.
            user_id: User identifier for creating new session. Required if
                session is None and session doesn't exist.

        Returns:
            Assigned message ID (integer starting from 1_000_000 to avoid collision with DB IDs).

        Raises:
            InvalidDataError: If session_id is not positive, message is None,
                or user_id is not provided when creating new session.
        """
        await self._validate_session_id(session_id)
        if message is None:
            raise InvalidDataError("message cannot be None")

        async with self._get_lock():
            if session_id not in self._sessions:
                # Check max_sessions limit BEFORE creating new session
                if len(self._sessions) >= self._max_sessions:
                    await self._evict_oldest_session()

                if session is None:
                    if user_id is None:
                        raise InvalidDataError(
                            "user_id is required when creating a new session"
                        )
                    session = Session(
                        session_id=session_id,
                        user_id=user_id,
                        memory_mode=MemoryMode.SHORT_TERM,
                        created_at=datetime.now(timezone.utc),
                        last_activity=datetime.now(timezone.utc),
                    )
                self._sessions[session_id] = SessionData(
                    session=session,
                    max_messages=self._max_messages,
                )

            session_data = self._sessions[session_id]
            
            # Assign unique negative ID to avoid collision with DB IDs
            assigned_id = next(self._message_id_counter)
            message_with_id = Message(
                message_id=assigned_id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                model_used=message.model_used,
                memory_mode_at_time=message.memory_mode_at_time,
            )
            
            session_data.messages.append(message_with_id)

            # Enforce max_messages limit
            while len(session_data.messages) > session_data.max_messages:
                session_data.messages.popleft()

            session_data.session.last_activity = datetime.now(timezone.utc)
            
            return assigned_id

    async def get_messages(self, session_id: int) -> List[Message]:
        """Get all messages for a session from memory.

        Args:
            session_id: The session identifier.

        Returns:
            List of messages in chronological order.
            Empty list if session doesn't exist.
        """
        await self._validate_session_id(session_id)

        async with self._get_lock():
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

        async with self._get_lock():
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

        async with self._get_lock():
            if session_id in self._sessions:
                return self._sessions[session_id].session
            return None

    async def cleanup_inactive(self) -> int:
        """Remove sessions that have been inactive longer than TTL.

        Returns:
            Number of sessions removed.
        """
        async with self._get_lock():
            now = datetime.now(timezone.utc)
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
        async with self._get_lock():
            return list(self._sessions.keys())

    async def get_size(self) -> int:
        """Return number of active sessions.

        Returns:
            Number of sessions in store.
        """
        async with self._get_lock():
            return len(self._sessions)

    async def update_message(self, message: Message) -> bool:
        """Update a message in the session's in-memory store.

        Args:
            message: Message entity with updated content.

        Returns:
            True if message was updated, False if not found.
        """
        await self._validate_session_id(message.session_id)

        async with self._get_lock():
            if message.session_id not in self._sessions:
                return False

            session_data = self._sessions[message.session_id]
            for i, stored_msg in enumerate(session_data.messages):
                if stored_msg.message_id == message.message_id:
                    # Replace the message at the same position
                    session_data.messages[i] = message
                    session_data.session.last_activity = datetime.now(timezone.utc)
                    return True

            return False

    async def delete_message(self, message_id: int, session_id: int) -> bool:
        """Delete a message from the session's in-memory store.

        Args:
            message_id: Message identifier to delete.
            session_id: Session identifier.

        Returns:
            True if message was deleted, False if not found.
        """
        await self._validate_session_id(session_id)

        async with self._get_lock():
            if session_id not in self._sessions:
                return False

            session_data = self._sessions[session_id]
            for i, stored_msg in enumerate(session_data.messages):
                if stored_msg.message_id == message_id:
                    session_data.messages.remove(stored_msg)
                    session_data.session.last_activity = datetime.now(timezone.utc)
                    return True

            return False
