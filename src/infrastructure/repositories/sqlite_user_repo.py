"""SQLite implementation of UserRepository."""

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

    Attributes:
        db_path: Path to SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Absolute path to SQLite database file.
        """
        self.db_path = db_path

    @asynccontextmanager
    async def _get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get database connection with proper lifecycle management.

        Yields:
            Async SQLite connection with row factory and foreign keys enabled.

        Note:
            Connection is automatically closed when context manager exits.
            Foreign keys are enabled for data integrity.
        """
        connection = await aiosqlite.connect(self.db_path, timeout=30.0)
        try:
            connection.row_factory = aiosqlite.Row
            # Enable foreign keys for referential integrity
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

            await db.execute(
                """
                INSERT INTO users (user_id, telegram_id, default_mode, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (user.user_id, user.telegram_id, user.default_mode.value),
            )
            await db.commit()
            logger.debug(f"User {user.user_id} created with telegram_id {user.telegram_id}")

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
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?;",
                (user.user_id,),
            )
            exists = await cursor.fetchone()

            if not exists:
                logger.warning(f"User {user.user_id} not found for update")
                raise UserNotFoundError(user_id=user.user_id)

            if user.telegram_id is None:
                raise ValueError("telegram_id cannot be set to None for update")

            await db.execute(
                """
                UPDATE users
                SET telegram_id = ?, default_mode = ?
                WHERE user_id = ?;
                """,
                (user.telegram_id, user.default_mode.value, user.user_id),
            )
            await db.commit()
            logger.debug(f"User {user.user_id} updated")
