"""Database connection management.

SECURITY NOTE: All SQL queries MUST use parameterized statements.
Never use f-strings or string concatenation with user input in SQL queries.
Example:
    ✅ CORRECT: await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    ❌ WRONG:   await db.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

from src.infrastructure.database.schema import (
    CREATE_INDEXES,
    CREATE_MESSAGES_TABLE,
    CREATE_SESSIONS_TABLE,
    CREATE_USERS_TABLE,
)

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database errors."""


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""


class DatabaseInitializationError(DatabaseError):
    """Raised when database initialization fails."""


def get_db_path() -> str:
    """Extract database path from DATABASE_URL.

    Returns:
        Absolute database file path.

    Raises:
        ValueError: If DATABASE_URL is not set or has unsupported format.
    """
    url = os.getenv("DATABASE_URL", "")

    if not url:
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please copy .env.example to .env and configure it."
        )

    # Normalize and extract path
    prefixes = [
        "sqlite+aiosqlite:///",
        "sqlite:///",
        "sqlite+aiosqlite://",
        "sqlite://",
    ]

    db_path = url
    for prefix in prefixes:
        if url.startswith(prefix):
            db_path = url[len(prefix) :]
            break
    else:
        raise ValueError(f"Unsupported database URL: {url}")

    if not db_path:
        raise ValueError(
            "Database path is empty. DATABASE_URL must include a valid path."
        )

    # Convert to absolute path if relative
    if not Path(db_path).is_absolute():
        db_path = str(Path(db_path).resolve())

    return db_path


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Get database connection.

    Yields:
        Async SQLite connection.

    Raises:
        DatabaseConnectionError: If database connection fails.
        ValueError: If DATABASE_URL is not configured.
    """
    db_path = get_db_path()

    try:
        connection = await aiosqlite.connect(db_path, timeout=30.0)
    except aiosqlite.Error as e:
        logger.error(f"Failed to connect to database at {db_path}: {e}")
        raise DatabaseConnectionError(
            f"Failed to connect to database at {db_path}: {e}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error connecting to database: {e}")
        raise DatabaseConnectionError(
            f"Unexpected error connecting to database: {e}"
        ) from e

    try:
        connection.row_factory = aiosqlite.Row

        # Enable foreign keys and verify
        await connection.execute("PRAGMA foreign_keys = ON;")
        result = await connection.execute("PRAGMA foreign_keys;")
        row = await result.fetchone()
        if not row or not row[0]:
            raise DatabaseConnectionError("Foreign keys could not be enabled")

        logger.debug(f"Database connection established: {db_path}")
        yield connection

    except aiosqlite.Error as e:
        logger.error(f"Database error during connection usage: {e}")
        raise DatabaseError(f"Database error: {e}") from e
    finally:
        try:
            await connection.close()
            logger.debug("Database connection closed")
        except aiosqlite.Error as e:
            logger.warning(f"Error closing database connection: {e}")


async def init_database() -> None:
    """Initialize database with schema.

    Creates all tables and indexes if they don't exist.
    All operations are wrapped in a single transaction for atomicity.

    Raises:
        DatabaseInitializationError: If database initialization fails.
    """
    async with get_db() as db:
        try:
            # Wrap all operations in a single transaction
            await db.execute("BEGIN TRANSACTION;")

            await db.execute(CREATE_USERS_TABLE)
            await db.execute(CREATE_SESSIONS_TABLE)
            await db.execute(CREATE_MESSAGES_TABLE)
            await db.execute(CREATE_INDEXES)

            await db.execute("COMMIT;")
            logger.info("Database initialized successfully")

        except aiosqlite.Error as e:
            await db.execute("ROLLBACK;")
            logger.error(f"Database initialization failed: {e}")
            raise DatabaseInitializationError(
                f"Failed to initialize database: {e}"
            ) from e
        except Exception as e:
            await db.execute("ROLLBACK;")
            logger.error(f"Unexpected error during database initialization: {e}")
            raise DatabaseInitializationError(
                f"Unexpected error during database initialization: {e}"
            ) from e
