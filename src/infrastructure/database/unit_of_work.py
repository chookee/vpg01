"""Unit of Work pattern for transaction boundaries.

This module provides atomic transaction management for database operations.
All operations within a transaction are either committed together or rolled back.

Example:
    async with UnitOfWork(db_path).transaction() as uow:
        # Create repositories that share the same connection
        msg_repo = uow.create_message_repo()
        sess_repo = uow.create_session_repo()
        
        await msg_repo.add(message)
        await sess_repo.create(session)
    # All operations committed atomically

Note:
    CURRENT LIMITATION (Stages 12-16):
    Repositories now accept optional connection parameter, but use cases
    are not yet integrated with UnitOfWork. This is acceptable for current
    use cases (single message operations without complex transactions).

    TODO (Stages 18-19):
    - Integrate UnitOfWork with RepositoryFactory
    - Add DI container for automatic dependency injection
    - Update controllers to use UnitOfWork for transactional use cases
    See: doc/plan.md milestones 18-19
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator

import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class UnitOfWork:
    """Transaction boundary manager for atomic operations.

    Provides a context manager that wraps multiple database operations
    in a single transaction. If any operation fails, all changes are
    rolled back.

    Attributes:
        db_path: Path to SQLite database file.

    Example:
        async with UnitOfWork(db_path).transaction() as uow:
            # Create repositories with shared connection
            msg_repo = uow.create_message_repo()
            await msg_repo.add(message)
        # Committed automatically

        try:
            async with UnitOfWork(db_path).transaction() as uow:
                msg_repo = uow.create_message_repo()
                await msg_repo.add(message)
                raise ValueError("Simulated error")
        except ValueError:
            # Rolled back automatically
    """

    db_path: str
    _connection: aiosqlite.Connection | None = field(default=None, init=False, repr=False)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection.

        Returns:
            Active database connection.
        """
        if self._connection is None:
            # Use isolation_level=None for manual transaction control
            self._connection = await aiosqlite.connect(
                self.db_path, timeout=30.0, isolation_level=None
            )
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
        return self._connection

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["UnitOfWork", None]:
        """Execute operations within a transaction.

        Yields:
            UnitOfWork instance with active connection.

        Raises:
            DatabaseError: If database operation fails.
        """
        db = await self._get_connection()

        transaction_started = False
        try:
            await db.execute("BEGIN;")
            transaction_started = True
            logger.debug("Transaction started")

            yield self

            await db.execute("COMMIT;")
            logger.debug("Transaction committed")

        except Exception as e:
            if transaction_started:
                try:
                    await db.execute("ROLLBACK;")
                    logger.debug("Transaction rolled back")
                except Exception as rollback_error:
                    logger.warning(f"Rollback failed: {rollback_error}")
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
            logger.debug("Transaction connection closed")

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active database connection.

        Returns:
            Active database connection.

        Raises:
            RuntimeError: If called outside of transaction context.
        """
        if self._connection is None:
            raise RuntimeError(
                "UnitOfWork must be used within 'async with' context"
            )
        return self._connection

    def create_message_repo(self) -> "MessageRepository":
        """Create message repository with current transaction connection.

        Returns:
            MessageRepository instance using the transaction's connection.

        Note:
            Repository created this way shares the connection with other
            repositories created in the same transaction. Changes are
            committed/rolled back together.
        """
        # Lazy import to avoid circular dependencies
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )

        return SQLiteMessageRepository(self.db_path, self._connection)

    def create_session_repo(self) -> "SessionRepository":
        """Create session repository with current transaction connection.

        Returns:
            SessionRepository instance using the transaction's connection.

        Note:
            Repository created this way shares the connection with other
            repositories created in the same transaction. Changes are
            committed/rolled back together.
        """
        # Lazy import to avoid circular dependencies
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )

        return SQLiteSessionRepository(self.db_path, self._connection)

    def create_user_repo(self) -> "UserRepository":
        """Create user repository with current transaction connection.

        Returns:
            UserRepository instance using the transaction's connection.

        Note:
            Repository created this way shares the connection with other
            repositories created in the same transaction. Changes are
            committed/rolled back together.
        """
        # Lazy import to avoid circular dependencies
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        return SQLiteUserRepository(self.db_path, self._connection)
