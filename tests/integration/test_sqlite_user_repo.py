"""Integration tests for SQLiteUserRepository."""

import pytest

from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.infrastructure.repositories.sqlite_user_repo import SQLiteUserRepository


@pytest.mark.asyncio
async def test_create_and_get_user_by_id(sqlite_user_repo: SQLiteUserRepository) -> None:
    """Test creating and retrieving a user by ID."""
    user = User(
        user_id=1,
        telegram_id=12345,
        default_mode=MemoryMode.SHORT_TERM,
    )

    await sqlite_user_repo.create(user)
    retrieved = await sqlite_user_repo.get_by_id(1)

    assert retrieved is not None
    assert retrieved.user_id == 1
    assert retrieved.telegram_id == 12345
    assert retrieved.default_mode == MemoryMode.SHORT_TERM


@pytest.mark.asyncio
async def test_create_and_get_user_by_telegram_id(
    sqlite_user_repo: SQLiteUserRepository,
) -> None:
    """Test retrieving a user by Telegram ID."""
    user = User(
        user_id=1,
        telegram_id=12345,
        default_mode=MemoryMode.LONG_TERM,
    )
    await sqlite_user_repo.create(user)

    retrieved = await sqlite_user_repo.get_by_telegram_id(12345)

    assert retrieved is not None
    assert retrieved.user_id == 1
    assert retrieved.default_mode == MemoryMode.LONG_TERM


@pytest.mark.asyncio
async def test_get_nonexistent_user_by_id(sqlite_user_repo: SQLiteUserRepository) -> None:
    """Test getting a user that doesn't exist."""
    result = await sqlite_user_repo.get_by_id(999)
    assert result is None


@pytest.mark.asyncio
async def test_get_nonexistent_user_by_telegram_id(
    sqlite_user_repo: SQLiteUserRepository,
) -> None:
    """Test getting a user by Telegram ID that doesn't exist."""
    result = await sqlite_user_repo.get_by_telegram_id(99999)
    assert result is None


@pytest.mark.asyncio
async def test_update_user(sqlite_user_repo: SQLiteUserRepository) -> None:
    """Test updating a user."""
    user = User(
        user_id=1,
        telegram_id=12345,
        default_mode=MemoryMode.NO_MEMORY,
    )
    await sqlite_user_repo.create(user)

    user.default_mode = MemoryMode.BOTH
    await sqlite_user_repo.update(user)

    retrieved = await sqlite_user_repo.get_by_id(1)
    assert retrieved is not None
    assert retrieved.default_mode == MemoryMode.BOTH


# =============================================================================
# Exception Handling Tests
# =============================================================================

@pytest.mark.asyncio
async def test_update_nonexistent_user_raises_error(
    sqlite_user_repo: SQLiteUserRepository,
) -> None:
    """Should raise UserNotFoundError when updating non-existent user."""
    from src.domain.exceptions import UserNotFoundError

    user = User(
        user_id=999,
        telegram_id=999,
        default_mode=MemoryMode.SHORT_TERM,
    )

    with pytest.raises(UserNotFoundError, match="User with id=999 not found"):
        await sqlite_user_repo.update(user)
