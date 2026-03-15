"""SQLite implementation of MessageRepository.

Note:
    This repository supports two modes of operation:
    1. Standalone — creates its own connection for each operation
    2. Transactional — uses an external connection from UnitOfWork

    For full transactional integrity (stages 18-19), repositories
    should be refactored to use a factory pattern with DI container.
    See: doc/plan.md milestones 18-19
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

import aiosqlite

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, MessageNotFoundError
from src.domain.interfaces.repositories import MessageRepository

logger = logging.getLogger(__name__)


class SQLiteMessageRepository(MessageRepository):
    """SQLite implementation of MessageRepository.

    Supports optional external connection for use with UnitOfWork.

    Attributes:
        db_path: Path to SQLite database file.
        _external_connection: Optional external connection (from UnitOfWork).
    """

    def __init__(
        self,
        db_path: str,
        connection: aiosqlite.Connection | None = None,
    ) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Absolute path to SQLite database file.
            connection: Optional external connection for transactional mode.
                If None, creates own connection for each operation.
        """
        self.db_path = db_path
        self._external_connection = connection

    @asynccontextmanager
    async def _get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get database connection with proper lifecycle management.

        Yields:
            Async SQLite connection with row factory and foreign keys enabled.

        Note:
            If external connection is provided (UnitOfWork mode), uses it
            and does NOT close it (caller manages lifecycle).
            Otherwise, creates own connection and closes when context exits.
            Foreign keys are enabled for data integrity.
        """
        if self._external_connection is not None:
            # Transactional mode: use external connection (don't close)
            self._external_connection.row_factory = aiosqlite.Row
            await self._external_connection.execute("PRAGMA foreign_keys = ON;")
            yield self._external_connection
        else:
            # Standalone mode: create own connection
            connection = await aiosqlite.connect(self.db_path, timeout=30.0)
            try:
                connection.row_factory = aiosqlite.Row
                await connection.execute("PRAGMA foreign_keys = ON;")
                yield connection
            finally:
                await connection.close()

    async def _init_db(self) -> None:
        """Initialize database schema."""
        async with self._get_connection() as db:
            # Create all tables for standalone testing
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    default_mode TEXT NOT NULL DEFAULT 'no_memory',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    memory_mode TEXT NOT NULL DEFAULT 'no_memory',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    model_used TEXT,
                    memory_mode_at_time TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);"
            )
            await db.commit()
            logger.info("Messages table initialized")

    async def add(self, message: Message) -> int:
        """Add a message to the repository.

        Args:
            message: Message entity to add.

        Returns:
            Assigned message_id for the inserted message.

        Raises:
            ValueError: If message validation fails.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                INSERT INTO messages (
                    session_id,
                    role,
                    content,
                    timestamp,
                    model_used,
                    memory_mode_at_time
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    message.session_id,
                    message.role,
                    message.content,
                    message.timestamp.isoformat(),
                    message.model_used,
                    message.memory_mode_at_time.value if message.memory_mode_at_time else None,
                ),
            )
            await db.commit()
            message_id = cursor.lastrowid
            if message_id is None:
                raise RuntimeError("Failed to get inserted message ID")
            logger.debug(f"Message {message_id} added to session {message.session_id}")
            return message_id

    async def get_by_session(self, session_id: int) -> list[Message]:
        """Get all messages for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages ordered by timestamp.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT message_id, session_id, role, content, timestamp, model_used, memory_mode_at_time
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC;
                """,
                (session_id,),
            )
            rows = await cursor.fetchall()

            messages: list[Message] = []
            for row in rows:
                memory_mode_value = row["memory_mode_at_time"]
                memory_mode: MemoryMode | None = None
                if memory_mode_value:
                    try:
                        memory_mode = MemoryMode(memory_mode_value)
                    except ValueError:
                        logger.warning(f"Unknown memory mode: {memory_mode_value}")

                timestamp_str = row["timestamp"]
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                else:
                    timestamp = timestamp_str or datetime.now(timezone.utc)

                message = Message(
                    message_id=row["message_id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=timestamp,
                    model_used=row["model_used"],
                    memory_mode_at_time=memory_mode,
                )
                messages.append(message)

            logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
            return messages

    async def get_by_id(self, message_id: int) -> Message | None:
        """Get a message by ID.

        Args:
            message_id: Message identifier.

        Returns:
            Message entity or None if not found.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT message_id, session_id, role, content, timestamp, model_used, memory_mode_at_time
                FROM messages
                WHERE message_id = ?;
                """,
                (message_id,),
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            memory_mode_value = row["memory_mode_at_time"]
            memory_mode: MemoryMode | None = None
            if memory_mode_value:
                try:
                    memory_mode = MemoryMode(memory_mode_value)
                except ValueError:
                    logger.warning(f"Unknown memory mode: {memory_mode_value}")

            timestamp_str = row["timestamp"]
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
            else:
                timestamp = timestamp_str or datetime.now(timezone.utc)

            message = Message(
                message_id=row["message_id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                timestamp=timestamp,
                model_used=row["model_used"],
                memory_mode_at_time=memory_mode,
            )
            logger.debug(f"Retrieved message {message_id}")
            return message

    async def update(self, message: Message) -> None:
        """Update an existing message.

        Args:
            message: Message entity with updated data.

        Raises:
            MessageNotFoundError: If message does not exist.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE messages
                SET content = ?, timestamp = ?, model_used = ?, memory_mode_at_time = ?
                WHERE message_id = ?;
                """,
                (
                    message.content,
                    message.timestamp.isoformat(),
                    message.model_used,
                    message.memory_mode_at_time.value if message.memory_mode_at_time else None,
                    message.message_id,
                ),
            )
            await db.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Message {message.message_id} not found for update")
                raise MessageNotFoundError(message.message_id)

            logger.debug(f"Message {message.message_id} updated")

    async def delete(self, message_id: int) -> None:
        """Delete a message by ID.

        Args:
            message_id: Message identifier to delete.

        Raises:
            MessageNotFoundError: If message does not exist.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM messages WHERE message_id = ?;",
                (message_id,),
            )
            await db.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Message {message_id} not found for deletion")
                raise MessageNotFoundError(message_id)

            logger.debug(f"Message {message_id} deleted")

    async def delete_by_session(self, session_id: int) -> None:
        """Delete all messages for a session.

        Args:
            session_id: Session identifier.
        """
        async with self._get_connection() as db:
            await db.execute(
                "DELETE FROM messages WHERE session_id = ?;",
                (session_id,),
            )
            await db.commit()
            logger.debug(f"All messages deleted for session {session_id}")

    async def get_by_sessions_batch(self, session_ids: list[int]) -> list[Message]:
        """Get messages for multiple sessions in one efficient query.

        Solves N+1 problem by fetching all messages in a single database round-trip.

        Args:
            session_ids: List of session identifiers.

        Returns:
            List of messages ordered by session_id and timestamp.

        Raises:
            InvalidDataError: If session_ids list is too large or contains invalid IDs.
        """
        if not session_ids:
            return []

        # Validate input size to prevent DoS via large queries
        if len(session_ids) > 1000:
            raise InvalidDataError(
                f"session_ids list too large: {len(session_ids)} (max 1000)"
            )

        # Validate all IDs are positive
        invalid_ids = [sid for sid in session_ids if sid <= 0]
        if invalid_ids:
            raise InvalidDataError(
                f"Invalid session_ids: {invalid_ids[:5]}{'...' if len(invalid_ids) > 5 else ''} "
                f"(must be positive)"
            )

        # Deduplicate to prevent redundant queries
        unique_ids = list(set(session_ids))

        async with self._get_connection() as db:
            # Build placeholders for IN clause
            placeholders = ",".join("?" * len(unique_ids))
            cursor = await db.execute(
                f"""
                SELECT message_id, session_id, role, content, timestamp, model_used, memory_mode_at_time
                FROM messages
                WHERE session_id IN ({placeholders})
                ORDER BY session_id, timestamp ASC;
                """,
                tuple(unique_ids),
            )
            rows = await cursor.fetchall()

            messages: list[Message] = []
            for row in rows:
                memory_mode_value = row["memory_mode_at_time"]
                memory_mode: MemoryMode | None = None
                if memory_mode_value:
                    try:
                        memory_mode = MemoryMode(memory_mode_value)
                    except ValueError:
                        logger.warning(f"Unknown memory mode: {memory_mode_value}")

                timestamp_str = row["timestamp"]
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
                else:
                    timestamp = timestamp_str or datetime.now(timezone.utc)

                message = Message(
                    message_id=row["message_id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=timestamp,
                    model_used=row["model_used"],
                    memory_mode_at_time=memory_mode,
                )
                messages.append(message)

            logger.debug(f"Retrieved {len(messages)} messages for {len(session_ids)} sessions")
            return messages
