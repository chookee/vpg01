"""Abstract factory for creating repository instances.

This module provides RepositoryFactory that creates repository instances
based on the database type configured in the application settings.

Supports both standalone and transactional modes:
- Standalone: Creates repositories with own connections
- Transactional: Creates repositories sharing a UnitOfWork connection

Example:
    >>> # Standalone mode
    >>> factory = RepositoryFactory(settings.database_type, settings.database_url)
    >>> message_repo = factory.create_message_repo()
    
    >>> # Transactional mode
    >>> async with UnitOfWork(db_path).transaction() as uow:
    ...     repos = factory.create_transactional_repos(uow.connection)
    ...     # All repos share the same transaction
"""

import logging
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

import aiosqlite

from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    UserRepository,
)

logger = logging.getLogger(__name__)

# Supported database types
DATABASE_TYPE_SQLITE: Final[str] = "sqlite"
DATABASE_TYPE_POSTGRESQL: Final[str] = "postgresql"


def extract_sqlite_path_from_url(database_url: str) -> str:
    """Extract database file path from SQLite URL.

    Args:
        database_url: SQLite connection URL (e.g., sqlite+aiosqlite:///./data/app.db).

    Returns:
        Absolute path to database file.

    Raises:
        ValueError: If URL scheme is not SQLite or path traversal detected.
    """
    from pathlib import Path

    prefixes = [
        "sqlite+aiosqlite:///",
        "sqlite:///",
        "sqlite+aiosqlite://",
        "sqlite://",
    ]

    db_path = database_url
    for prefix in prefixes:
        if database_url.startswith(prefix):
            db_path = database_url[len(prefix) :]
            break

    # Security: Prevent path traversal attacks
    # Check for '..' in the original path - this is the primary security check
    if ".." in db_path:
        raise ValueError(
            f"Database path must not contain '..' (path traversal not allowed): {db_path}"
        )

    # Resolve to absolute path (resolves symlinks and relative paths)
    try:
        resolved_path = Path(db_path).resolve()
    except (ValueError, OSError) as e:
        raise ValueError(f"Invalid database path: {db_path}") from e

    # Ensure the resolved path is absolute
    if not resolved_path.is_absolute():
        raise ValueError(
            f"Database path must be absolute: {db_path}"
        )

    return str(resolved_path)


@dataclass
class TransactionalRepositories:
    """Container for transactional repository instances.
    
    All repositories in this container share the same database connection
    and participate in a single transaction.
    
    Attributes:
        message_repo: Transactional message repository.
        session_repo: Transactional session repository.
        user_repo: Transactional user repository.
        connection: Shared database connection.
    """
    
    message_repo: MessageRepository
    session_repo: SessionRepository
    user_repo: UserRepository
    connection: aiosqlite.Connection


@dataclass
class RepositoryFactory:
    """Abstract factory for creating repository instances.

    Creates repository instances based on the configured database type.
    Currently supports SQLite, with PostgreSQL available for future extension.

    Attributes:
        database_type: Type of database (sqlite, postgresql).
        database_url: Database connection URL.

    Raises:
        ValueError: If database type is unsupported or URL is invalid.

    Example:
        >>> factory = RepositoryFactory("sqlite", "sqlite+aiosqlite:///./data/app.db")
        >>> message_repo = factory.create_message_repo()
    """

    database_type: str
    database_url: str

    def __post_init__(self) -> None:
        """Validate factory configuration after initialization."""
        self._validate_database_type()
        self._validate_database_url()

    def _validate_database_type(self) -> None:
        """Validate database type is supported.

        Raises:
            ValueError: If database type is not supported.
        """
        supported_types = {DATABASE_TYPE_SQLITE, DATABASE_TYPE_POSTGRESQL}
        if self.database_type not in supported_types:
            raise ValueError(
                f"Unsupported database type: {self.database_type}. "
                f"Supported types: {', '.join(supported_types)}"
            )

    def _validate_database_url(self) -> None:
        """Validate database URL format.

        Raises:
            ValueError: If database URL is empty or has invalid format.
        """
        if not self.database_url:
            raise ValueError("Database URL cannot be empty")

        try:
            parsed = urlparse(self.database_url)
            if not parsed.scheme:
                raise ValueError("Database URL must include scheme")
        except Exception as e:
            raise ValueError(f"Invalid database URL format: {e}") from e

    def create_message_repo(self) -> MessageRepository:
        """Create message repository instance.

        Returns:
            MessageRepository instance for the configured database type.

        Raises:
            NotImplementedError: If database type is not yet implemented.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_message_repo()
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL message repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def create_session_repo(self) -> SessionRepository:
        """Create session repository instance.

        Returns:
            SessionRepository instance for the configured database type.

        Raises:
            NotImplementedError: If database type is not yet implemented.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_session_repo()
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL session repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def create_user_repo(self) -> UserRepository:
        """Create user repository instance.

        Returns:
            UserRepository instance for the configured database type.

        Raises:
            NotImplementedError: If database type is not yet implemented.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_user_repo()
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL user repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def create_transactional_repos(
        self,
        connection: aiosqlite.Connection,
    ) -> TransactionalRepositories:
        """Create all repositories with shared transactional connection.

        Use this method within a UnitOfWork transaction to ensure all
        repository operations participate in the same transaction.

        Args:
            connection: Active database connection from UnitOfWork.

        Returns:
            TransactionalRepositories container with all repositories
            sharing the same connection.

        Example:
            async with UnitOfWork(db_path).transaction() as uow:
                repos = factory.create_transactional_repos(uow.connection)
                await repos.message_repo.add(message)
                await repos.session_repo.create(session)
            # All operations committed atomically
        """
        return TransactionalRepositories(
            message_repo=self._create_sqlite_message_repo_with_connection(
                connection
            ),
            session_repo=self._create_sqlite_session_repo_with_connection(
                connection
            ),
            user_repo=self._create_sqlite_user_repo_with_connection(connection),
            connection=connection,
        )

    def create_message_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> MessageRepository:
        """Create message repository with specific connection.

        Args:
            connection: Database connection to use (e.g., from UnitOfWork).

        Returns:
            MessageRepository instance using the provided connection.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_message_repo_with_connection(connection)
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL message repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def create_session_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> SessionRepository:
        """Create session repository with specific connection.

        Args:
            connection: Database connection to use (e.g., from UnitOfWork).

        Returns:
            SessionRepository instance using the provided connection.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_session_repo_with_connection(connection)
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL session repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def create_user_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> UserRepository:
        """Create user repository with specific connection.

        Args:
            connection: Database connection to use (e.g., from UnitOfWork).

        Returns:
            UserRepository instance using the provided connection.
        """
        if self.database_type == DATABASE_TYPE_SQLITE:
            return self._create_sqlite_user_repo_with_connection(connection)
        elif self.database_type == DATABASE_TYPE_POSTGRESQL:
            raise NotImplementedError(
                "PostgreSQL user repository not yet implemented"
            )
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def _create_sqlite_message_repo(self) -> MessageRepository:
        """Create SQLite message repository.

        Returns:
            SQLiteMessageRepository instance.
        """
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )

        # Extract path from URL for SQLite
        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating SQLite message repository: {db_path}")
        return SQLiteMessageRepository(db_path)

    def _create_sqlite_message_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> MessageRepository:
        """Create SQLite message repository with specific connection.

        Args:
            connection: Active database connection (e.g., from UnitOfWork).

        Returns:
            SQLiteMessageRepository instance using the connection.
        """
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )

        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating transactional SQLite message repository: {db_path}")
        return SQLiteMessageRepository(db_path, connection=connection)

    def _create_sqlite_session_repo(self) -> SessionRepository:
        """Create SQLite session repository.

        Returns:
            SQLiteSessionRepository instance.
        """
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )

        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating SQLite session repository: {db_path}")
        return SQLiteSessionRepository(db_path)

    def _create_sqlite_session_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> SessionRepository:
        """Create SQLite session repository with specific connection.

        Args:
            connection: Active database connection (e.g., from UnitOfWork).

        Returns:
            SQLiteSessionRepository instance using the connection.
        """
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )

        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating transactional SQLite session repository: {db_path}")
        return SQLiteSessionRepository(db_path, connection=connection)

    def _create_sqlite_user_repo(self) -> UserRepository:
        """Create SQLite user repository.

        Returns:
            SQLiteUserRepository instance.
        """
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating SQLite user repository: {db_path}")
        return SQLiteUserRepository(db_path)

    def _create_sqlite_user_repo_with_connection(
        self,
        connection: aiosqlite.Connection,
    ) -> UserRepository:
        """Create SQLite user repository with specific connection.

        Args:
            connection: Active database connection (e.g., from UnitOfWork).

        Returns:
            SQLiteUserRepository instance using the connection.
        """
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        db_path = self._extract_sqlite_path()
        logger.debug(f"Creating transactional SQLite user repository: {db_path}")
        return SQLiteUserRepository(db_path, connection=connection)

    def _extract_sqlite_path(self) -> str:
        """Extract database file path from SQLite URL.

        Returns:
            Absolute path to SQLite database file.

        Raises:
            ValueError: If URL scheme is not SQLite.
        """
        return extract_sqlite_path_from_url(self.database_url)
