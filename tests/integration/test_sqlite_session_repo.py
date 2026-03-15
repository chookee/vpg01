"""Integration tests for SQLiteSessionRepository."""

import pytest

from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.infrastructure.repositories.sqlite_session_repo import SQLiteSessionRepository


@pytest.mark.asyncio
async def test_create_and_get_session(sqlite_session_repo: SQLiteSessionRepository) -> None:
    """Test creating and retrieving a session."""
    session = Session(
        session_id=1,
        user_id=1,
        memory_mode=MemoryMode.LONG_TERM,
    )

    await sqlite_session_repo.create(session)
    retrieved = await sqlite_session_repo.get(1)

    assert retrieved is not None
    assert retrieved.session_id == 1
    assert retrieved.user_id == 1
    assert retrieved.memory_mode == MemoryMode.LONG_TERM


@pytest.mark.asyncio
async def test_get_nonexistent_session(sqlite_session_repo: SQLiteSessionRepository) -> None:
    """Test getting a session that doesn't exist."""
    result = await sqlite_session_repo.get(999)
    assert result is None


@pytest.mark.asyncio
async def test_update_mode(sqlite_session_repo: SQLiteSessionRepository) -> None:
    """Test updating session memory mode."""
    session = Session(
        session_id=1,
        user_id=1,
        memory_mode=MemoryMode.NO_MEMORY,
    )
    await sqlite_session_repo.create(session)

    await sqlite_session_repo.update_mode(1, MemoryMode.BOTH)

    retrieved = await sqlite_session_repo.get(1)
    assert retrieved is not None
    assert retrieved.memory_mode == MemoryMode.BOTH


@pytest.mark.asyncio
async def test_delete_session(sqlite_session_repo: SQLiteSessionRepository) -> None:
    """Test deleting a session."""
    session = Session(session_id=1, user_id=1)
    await sqlite_session_repo.create(session)

    await sqlite_session_repo.delete(1)

    result = await sqlite_session_repo.get(1)
    assert result is None
