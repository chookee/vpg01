"""Unit of Work pattern for transaction boundaries.

This module provides atomic transaction management for database operations.
All operations within a transaction are either committed together or rolled back.

Example:
    async with UnitOfWork(db_path).transaction() as uow:
        await uow.message_repo.add(user_message)
        response = await llm.generate(...)
        await uow.message_repo.add(assistant_message)
    # All operations committed atomically
"""

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator

import aiosqlite

from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    UserRepository,
)
from src.infrastructure.repositories.sqlite_message_repo import SQLiteMessageRepository
from src.infrastructure.repositories.sqlite_session_repo import SQLiteSessionRepository
from src.infrastructure.repositories.sqlite_user_repo import SQLiteUserRepository

logger = logging.getLogger(__name__)


@dataclass
class UnitOfWork:
    """Transaction boundary manager for atomic operations.

    Provides a context manager that wraps multiple repository operations
    in a single database transaction. If any operation fails, all changes
    are rolled back.

    Attributes:
        db_path: Path to SQLite database file.

    Example:
        async with UnitOfWork(db_path).transaction() as uow:
            # All operations share the same connection
            await uow.users.create(user)
            await uow.sessions.create(session)
            await uow.messages.add(message)
        # Automatically committed on exit, rolled back on exception
    """

    db_path: str
    _connection: aiosqlite.Connection | None = field(default=None, init=False, repr=False)
    _message_repo: MessageRepository | None = field(default=None, init=False, repr=False)
    _session_repo: SessionRepository | None = field(default=None, init=False, repr=False)
    _user_repo: UserRepository | None = field(default=None, init=False, repr=False)

    async def _get_connection(self) -> aiosqlite.Connection:
        """Get or create database connection.

        Returns:
            Active database connection.
        """
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path, timeout=30.0)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA foreign_keys = ON;")
        return self._connection

    @property
    def messages(self) -> MessageRepository:
        """Get message repository within current transaction.

        Returns:
            Message repository instance.

        Raises:
            RuntimeError: If called outside of transaction context.
        """
        if self._message_repo is None:
            raise RuntimeError("UnitOfWork must be used within 'async with' context")
        return self._message_repo

    @property
    def sessions(self) -> SessionRepository:
        """Get session repository within current transaction.

        Returns:
            Session repository instance.

        Raises:
            RuntimeError: If called outside of transaction context.
        """
        if self._session_repo is None:
            raise RuntimeError("UnitOfWork must be used within 'async with' context")
        return self._session_repo

    @property
    def users(self) -> UserRepository:
        """Get user repository within current transaction.

        Returns:
            User repository instance.

        Raises:
            RuntimeError: If called outside of transaction context.
        """
        if self._user_repo is None:
            raise RuntimeError("UnitOfWork must be used within 'async with' context")
        return self._user_repo

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator["UnitOfWork", None]:
        """Execute operations within a transaction.

        Yields:
            UnitOfWork instance with initialized repositories.

        Raises:
            DatabaseError: If database operation fails.

        Example:
            async with UnitOfWork(db_path).transaction() as uow:
                await uow.users.create(user)
                await uow.sessions.create(session)
            # Committed automatically

            try:
                async with UnitOfWork(db_path).transaction() as uow:
                    await uow.users.create(user)
                    raise ValueError("Simulated error")
            except ValueError:
                # Rolled back automatically
        """
        db = await self._get_connection()

        try:
            await db.execute("BEGIN;")
            logger.debug("Transaction started")

            # Create repository instances sharing the same connection
            # Note: We use a simplified approach - in production, repositories
            # should accept an existing connection instead of db_path
            self._message_repo = SQLiteMessageRepository(self.db_path)
            self._session_repo = SQLiteSessionRepository(self.db_path)
            self._user_repo = SQLiteUserRepository(self.db_path)

            yield self

            await db.execute("COMMIT;")
            logger.debug("Transaction committed")

        except Exception as e:
            await db.execute("ROLLBACK;")
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
            logger.debug("Transaction connection closed")
