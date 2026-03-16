"""Session manager for desktop application.

This module provides automatic session creation and management
for the desktop application, eliminating the need for manual
session setup.

Example:
    >>> manager = DesktopSessionManager(db_path)
    >>> session_id = await manager.get_or_create_session()
    >>> print(f"Using session: {session_id}")
"""

import logging
from pathlib import Path

from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.infrastructure.database.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

# Desktop app uses a fixed "user" for single-user mode.
# Using a special positive ID for desktop-only users (negative Telegram IDs are invalid).
# Range 900000000-999999999 is reserved for non-Telegram users (avoiding overflow).
DESKTOP_USER_TELEGRAM_ID = 999999999  # Special ID for desktop-only users


class DesktopSessionManager:
    """Manages session creation and retrieval for desktop app.

    Provides automatic session creation on first launch,
    eliminating the need for manual setup or Telegram bot
    interaction.

    Attributes:
        db_path: Path to SQLite database file.
        default_mode: Default memory mode for new sessions.

    Example:
        >>> manager = DesktopSessionManager("./data/app.db")
        >>> session_id = await manager.get_or_create_session()
    """

    def __init__(
        self,
        db_path: str,
        default_mode: MemoryMode = MemoryMode.SHORT_TERM,
    ) -> None:
        """Initialize DesktopSessionManager.

        Args:
            db_path: Path to SQLite database file.
            default_mode: Default memory mode for new sessions.
                Defaults to SHORT_TERM for interactive desktop use.
        """
        self._db_path = db_path
        self._default_mode = default_mode

    async def get_or_create_session(self) -> int:
        """Get existing session for desktop user or create new one.

        This method:
        1. Checks if a desktop user exists (telegram_id=0)
        2. If not, creates the user
        3. Checks if the user has an active session
        4. If not, creates a new session with default mode
        5. Returns the session ID

        Returns:
            Session ID (integer) for use with controllers.

        Raises:
            RuntimeError: If database operation fails.
            ValueError: If session creation fails.

        Note:
            This method is idempotent - calling it multiple times
            returns the same session ID for the same database.
        """
        try:
            async with UnitOfWork(self._db_path).transaction() as uow:
                repos = uow  # Use uow directly to create repos

                # Create repositories within transaction
                user_repo = uow.create_user_repo()
                session_repo = uow.create_session_repo()

                # Try to get existing desktop user
                user = await user_repo.get_by_telegram_id(DESKTOP_USER_TELEGRAM_ID)

                if user is None:
                    # Create new desktop user
                    user = User(
                        telegram_id=DESKTOP_USER_TELEGRAM_ID,
                        default_mode=self._default_mode,
                    )
                    await user_repo.create(user)
                    logger.debug("Created new desktop user")

                    # Refresh user to get assigned ID
                    user = await user_repo.get_by_telegram_id(DESKTOP_USER_TELEGRAM_ID)
                    if user is None or user.user_id is None:
                        raise RuntimeError("Failed to retrieve created desktop user")
                else:
                    logger.debug(f"Found existing desktop user: {user.user_id}")

                # Try to get existing session for user
                session = await session_repo.get_by_user_id(user.user_id)

                if session is None:
                    # Create new session
                    session = Session(
                        user_id=user.user_id,
                        memory_mode=self._default_mode,
                    )
                    await session_repo.create(session)
                    logger.debug(
                        f"Created new session for desktop user {user.user_id}"
                    )

                    # Refresh session to get assigned ID
                    session = await session_repo.get_by_user_id(user.user_id)
                    if session is None or session.session_id is None:
                        raise ValueError(
                            f"Failed to retrieve created session for user {user.user_id}"
                        )
                else:
                    logger.debug(f"Found existing session: {session.session_id}")

                # At this point session_id is guaranteed to be set
                logger.info(f"Desktop session ready: session_id={session.session_id}")
                return session.session_id

        except Exception as e:
            logger.exception(f"Failed to get/create desktop session: {e}")
            raise RuntimeError(f"Failed to initialize desktop session: {e}") from e

    async def get_session_info(self, session_id: int) -> dict:
        """Get information about a session.

        Args:
            session_id: Session identifier.

        Returns:
            Dictionary with session information:
            - session_id: Session ID
            - memory_mode: Current memory mode
            - message_count: Number of messages in session
            - user_id: Owner user ID

        Raises:
            ValueError: If session not found.
        """
        try:
            async with UnitOfWork(self._db_path).transaction() as uow:
                session_repo = uow.create_session_repo()
                message_repo = uow.create_message_repo()

                session = await session_repo.get(session_id)
                if session is None:
                    raise ValueError(f"Session {session_id} not found")

                # Count messages in session
                messages = await message_repo.get_by_session(session_id)

                return {
                    "session_id": session.session_id,
                    "memory_mode": session.memory_mode.value,
                    "message_count": len(messages),
                    "user_id": session.user_id,
                }

        except Exception as e:
            logger.exception(f"Failed to get session info: {e}")
            raise


async def initialize_desktop_session(db_path: str) -> int:
    """Convenience function to initialize desktop session.

    Args:
        db_path: Path to SQLite database file.

    Returns:
        Session ID for use with desktop app controllers.

    Example:
        >>> from src.interfaces.desktop_app.session_manager import (
        ...     initialize_desktop_session
        ... )
        >>> session_id = await initialize_desktop_session("./data/app.db")
    """
    manager = DesktopSessionManager(db_path)
    return await manager.get_or_create_session()
