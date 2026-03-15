"""Pytest fixtures and configuration for VPg01 tests."""

from datetime import datetime, timezone
from typing import AsyncGenerator, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.application.dtos import SessionDTO
from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    UserRepository,
)


# =============================================================================
# Mock Repositories (Unit Testing)
# =============================================================================


@pytest.fixture
def mock_message_repository() -> MessageRepository:
    """Create a mock message repository for unit testing.

    Returns:
        MagicMock implementing MessageRepository protocol.
    """
    mock = MagicMock(spec=MessageRepository)
    mock.add = AsyncMock()
    mock.get_by_session = AsyncMock(return_value=[])
    mock.get_by_id = AsyncMock(return_value=None)
    mock.update = AsyncMock()
    mock.delete = AsyncMock()
    mock.delete_by_session = AsyncMock()
    mock.get_by_sessions_batch = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_session_repository() -> SessionRepository:
    """Create a mock session repository for unit testing.

    Returns:
        MagicMock implementing SessionRepository protocol.
    """
    mock = MagicMock(spec=SessionRepository)
    mock.create = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.update_mode = AsyncMock()
    mock.delete = AsyncMock()
    return mock


@pytest.fixture
def mock_user_repository() -> UserRepository:
    """Create a mock user repository for unit testing.

    Returns:
        MagicMock implementing UserRepository protocol.
    """
    mock = MagicMock(spec=UserRepository)
    mock.create = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_telegram_id = AsyncMock(return_value=None)
    mock.update = AsyncMock()
    return mock


# =============================================================================
# Test Data Factories
# =============================================================================


@pytest.fixture
def user_factory() -> Callable[..., User]:
    """Factory for creating test User entities.

    Returns:
        Callable that creates User instances with customizable parameters.
    """

    def _create_user(
        user_id: int = 1,
        telegram_id: int | None = None,
        default_mode: MemoryMode = MemoryMode.SHORT_TERM,
    ) -> User:
        return User(
            user_id=user_id,
            telegram_id=telegram_id,
            default_mode=default_mode,
        )

    return _create_user


@pytest.fixture
def session_factory() -> Callable[..., Session]:
    """Factory for creating test Session entities.

    Returns:
        Callable that creates Session instances with customizable parameters.
    """

    def _create_session(
        session_id: int = 1,
        user_id: int = 1,
        memory_mode: MemoryMode = MemoryMode.SHORT_TERM,
    ) -> Session:
        return Session(
            session_id=session_id,
            user_id=user_id,
            memory_mode=memory_mode,
        )

    return _create_session


@pytest.fixture
def message_factory() -> Callable[..., Message]:
    """Factory for creating test Message entities.

    Returns:
        Callable that creates Message instances with customizable parameters.
    """

    def _create_message(
        message_id: int = 1,
        session_id: int = 1,
        role: str = "user",
        content: str = "Test message",
        model_used: str | None = None,
        memory_mode_at_time: MemoryMode | None = None,
    ) -> Message:
        return Message(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            model_used=model_used,
            memory_mode_at_time=memory_mode_at_time,
        )

    return _create_message


# =============================================================================
# Use Case Test Helpers
# =============================================================================


def create_test_message(
    message_id: int = 1,
    session_id: int = 1,
    role: str = "user",
    content: str = "Test message",
    timestamp: datetime | None = None,
    model_used: str | None = None,
    memory_mode_at_time: MemoryMode | None = None,
) -> Message:
    """Helper function to create test Message entities.

    Args:
        message_id: Message identifier. Defaults to 1.
        session_id: Session identifier. Defaults to 1.
        role: Message role ('user' or 'assistant'). Defaults to 'user'.
        content: Message content. Defaults to 'Test message'.
        timestamp: Message timestamp. Defaults to current UTC time.
        model_used: Model name used for generation.
        memory_mode_at_time: Memory mode at message creation time.

    Returns:
        Message instance with specified parameters.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    return Message(
        message_id=message_id,
        session_id=session_id,
        role=role,
        content=content,
        timestamp=timestamp,
        model_used=model_used,
        memory_mode_at_time=memory_mode_at_time,
    )


def create_test_session_dto(
    session_id: int = 1,
    user_id: int = 1,
    mode: MemoryMode = MemoryMode.SHORT_TERM,
) -> SessionDTO:
    """Helper function to create test SessionDTO instances.

    Args:
        session_id: Session identifier. Defaults to 1.
        user_id: User identifier. Defaults to 1.
        mode: Memory mode. Defaults to SHORT_TERM.

    Returns:
        SessionDTO instance with specified parameters.
    """
    now = datetime.now(timezone.utc)
    return SessionDTO(
        session_id=session_id,
        user_id=user_id,
        memory_mode=mode,
        created_at=now,
        last_activity=now,
    )


# =============================================================================
# Integration Test Fixtures (SQLite)
# =============================================================================


@pytest_asyncio.fixture(scope="function")
async def temp_db_path(tmp_path) -> AsyncGenerator[str, None]:
    """Create a temporary SQLite database path for integration tests.

    Args:
        tmp_path: Pytest temporary directory fixture.

    Yields:
        Path to temporary database file (not URL).
    """
    db_path = tmp_path / "test.db"
    try:
        yield str(db_path)
    finally:
        # Cleanup is handled by pytest's tmp_path fixture
        pass


@pytest_asyncio.fixture(scope="function")
async def sqlite_message_repo(
    temp_db_path: str,
) -> AsyncGenerator[MessageRepository, None]:
    """Create SQLite message repository with temporary database.

    Args:
        temp_db_path: Path to temporary database.

    Yields:
        SQLiteMessageRepository instance.
    """
    # Lazy import to avoid circular dependencies
    import aiosqlite

    from src.infrastructure.repositories.sqlite_message_repo import (
        SQLiteMessageRepository,
    )

    # Pre-create tables with parent records for foreign key constraints
    async with aiosqlite.connect(temp_db_path, timeout=30.0) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
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
        # Create parent records for tests
        await db.execute(
            "INSERT INTO users (user_id, telegram_id, default_mode) VALUES (1, 123, 'short_term');"
        )
        await db.execute(
            "INSERT INTO sessions (session_id, user_id, memory_mode) VALUES (1, 1, 'short_term');"
        )
        await db.commit()

    repo = SQLiteMessageRepository(temp_db_path)
    try:
        yield repo
    finally:
        # Connection is closed automatically when repo goes out of scope
        # Database file is cleaned up by tmp_path fixture
        pass


@pytest_asyncio.fixture(scope="function")
async def sqlite_session_repo(
    temp_db_path: str,
) -> AsyncGenerator[SessionRepository, None]:
    """Create SQLite session repository with temporary database.

    Args:
        temp_db_path: Path to temporary database.

    Yields:
        SQLiteSessionRepository instance.
    """
    import aiosqlite

    from src.infrastructure.repositories.sqlite_session_repo import (
        SQLiteSessionRepository,
    )

    # Pre-create tables with parent records for foreign key constraints
    async with aiosqlite.connect(temp_db_path, timeout=30.0) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
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
        # Create parent record for tests
        await db.execute(
            "INSERT INTO users (user_id, telegram_id, default_mode) VALUES (1, 123, 'short_term');"
        )
        await db.commit()

    repo = SQLiteSessionRepository(temp_db_path)
    try:
        yield repo
    finally:
        pass


@pytest_asyncio.fixture(scope="function")
async def sqlite_user_repo(
    temp_db_path: str,
) -> AsyncGenerator[UserRepository, None]:
    """Create SQLite user repository with temporary database.

    Args:
        temp_db_path: Path to temporary database.

    Yields:
        SQLiteUserRepository instance.
    """
    from src.infrastructure.repositories.sqlite_user_repo import SQLiteUserRepository

    repo = SQLiteUserRepository(temp_db_path)
    await repo._init_db()
    try:
        yield repo
    finally:
        pass
