"""SQLite implementation of UserRepository.

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
from typing import AsyncGenerator

import aiosqlite

from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.exceptions import UserNotFoundError
from src.domain.interfaces.repositories import UserRepository

logger = logging.getLogger(__name__)


class SQLiteUserRepository(UserRepository):
    """SQLite implementation of UserRepository.

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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    default_mode TEXT NOT NULL DEFAULT 'no_memory',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);"
            )
            await db.commit()
            logger.info("Users table initialized")

    async def create(self, user: User) -> None:
        """Create a new user.

        Args:
            user: User entity to create.

        Raises:
            ValueError: If telegram_id is None.
        """
        async with self._get_connection() as db:
            if user.telegram_id is None:
                raise ValueError("telegram_id cannot be None for user creation")

            # user_id can be None for new entities - let SQLite assign it via AUTOINCREMENT
            await db.execute(
                """
                INSERT INTO users (telegram_id, default_mode, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP);
                """,
                (user.telegram_id, user.default_mode.value),
            )
            await db.commit()
            logger.debug(f"User created with telegram_id {user.telegram_id}")

    async def get_by_id(self, user_id: int) -> User | None:
        """Get a user by ID.

        Args:
            user_id: User identifier.

        Returns:
            User entity or None if not found.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT user_id, telegram_id, default_mode, created_at
                FROM users
                WHERE user_id = ?;
                """,
                (user_id,),
            )
            row = await cursor.fetchone()

            if not row:
                logger.debug(f"User {user_id} not found")
                return None

            default_mode = MemoryMode(row["default_mode"])

            user = User(
                user_id=row["user_id"],
                telegram_id=row["telegram_id"],
                default_mode=default_mode,
            )
            logger.debug(f"User {user_id} retrieved")
            return user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Get a user by Telegram ID.

        Args:
            telegram_id: Telegram identifier.

        Returns:
            User entity or None if not found.
        """
        async with self._get_connection() as db:
            cursor = await db.execute(
                """
                SELECT user_id, telegram_id, default_mode, created_at
                FROM users
                WHERE telegram_id = ?;
                """,
                (telegram_id,),
            )
            row = await cursor.fetchone()

            if not row:
                logger.debug(f"User with telegram_id {telegram_id} not found")
                return None

            default_mode = MemoryMode(row["default_mode"])

            user = User(
                user_id=row["user_id"],
                telegram_id=row["telegram_id"],
                default_mode=default_mode,
            )
            logger.debug(f"User with telegram_id {telegram_id} retrieved (user_id={user.user_id})")
            return user

    async def update(self, user: User) -> None:
        """Update an existing user.

        Args:
            user: User entity with updated data.

        Raises:
            UserNotFoundError: If user does not exist.
            ValueError: If telegram_id is None.
        """
        async with self._get_connection() as db:
            if user.telegram_id is None:
                raise ValueError("telegram_id cannot be set to None for update")

            cursor = await db.execute(
                """
                UPDATE users
                SET telegram_id = ?, default_mode = ?
                WHERE user_id = ?;
                """,
                (user.telegram_id, user.default_mode.value, user.user_id),
            )
            await db.commit()

            if cursor.rowcount == 0:
                logger.warning(f"User {user.user_id} not found for update")
                raise UserNotFoundError(user_id=user.user_id)

            logger.debug(f"User {user.user_id} updated")
