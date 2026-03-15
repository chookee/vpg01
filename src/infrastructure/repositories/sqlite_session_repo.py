"""SQLite implementation of SessionRepository.

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

from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.domain.exceptions import SessionNotFoundError
from src.domain.interfaces.repositories import SessionRepository

logger = logging.getLogger(__name__)


class SQLiteSessionRepository(SessionRepository):
    """SQLite implementation of SessionRepository.

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
                "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity);"
            )
            await db.commit()
            logger.info("Sessions table initialized")

    async def create(self, session: Session) -> None:
        """Create a new session.

        Args:
            session: Session entity to create.
        """
        async with self._get_connection() as db:
            await db.execute(
                """
                INSERT INTO sessions (
                    session_id,
                    user_id,
                    memory_mode,
                    created_at,
                    last_activity
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.memory_mode.value,
                    session.created_at.isoformat(),
                    session.last_activity.isoformat(),
                ),
            )
            await db.commit()
            logger.debug(f"Session {session.session_id} created for user {session.user_id}")

    async def get(self, session_id: int) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session entity or None if not found.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT session_id, user_id, memory_mode, created_at, last_activity
                FROM sessions
                WHERE session_id = ?;
                """,
                (session_id,),
            )
            row = await cursor.fetchone()

            if not row:
                logger.debug(f"Session {session_id} not found")
                return None

            memory_mode = MemoryMode(row["memory_mode"])

            created_at_str = row["created_at"]
            if isinstance(created_at_str, str):
                created_at = datetime.fromisoformat(created_at_str).replace(tzinfo=timezone.utc)
            else:
                created_at = created_at_str or datetime.now(timezone.utc)

            last_activity_str = row["last_activity"]
            if isinstance(last_activity_str, str):
                last_activity = datetime.fromisoformat(last_activity_str).replace(tzinfo=timezone.utc)
            else:
                last_activity = last_activity_str or datetime.now(timezone.utc)

            session = Session(
                session_id=row["session_id"],
                user_id=row["user_id"],
                memory_mode=memory_mode,
                created_at=created_at,
                last_activity=last_activity,
            )
            logger.debug(f"Session {session_id} retrieved")
            return session

    async def update_mode(self, session_id: int, memory_mode: MemoryMode) -> None:
        """Update session memory mode.

        Args:
            session_id: Session identifier.
            memory_mode: New memory mode.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                UPDATE sessions
                SET memory_mode = ?, last_activity = ?
                WHERE session_id = ?;
                """,
                (memory_mode.value, datetime.now(timezone.utc).isoformat(), session_id),
            )
            await db.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Session {session_id} not found for mode update")
                raise SessionNotFoundError(session_id)

            logger.debug(f"Session {session_id} mode updated to {memory_mode.value}")

    async def delete(self, session_id: int) -> None:
        """Delete a session by ID.

        Args:
            session_id: Session identifier to delete.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                "DELETE FROM sessions WHERE session_id = ?;",
                (session_id,),
            )
            await db.commit()

            if cursor.rowcount == 0:
                logger.warning(f"Session {session_id} not found for deletion")
                raise SessionNotFoundError(session_id)

            logger.debug(f"Session {session_id} deleted")
