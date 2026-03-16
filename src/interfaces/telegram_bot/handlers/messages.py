"""Message handlers for Telegram bot.

This module handles incoming text messages and processes them
through the application's ProcessMessage use case.

Example:
    >>> dp = Dispatcher()
    >>> register_message_handlers(dp)
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from src.application.use_cases.process_message import ProcessMessage
from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.exceptions import RepositoryError, SessionNotFoundError
from src.domain.interfaces.repositories import SessionRepository, UserRepository
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

from ..controllers.message_controller import MessageController

if TYPE_CHECKING:
    from src.main import ApplicationContainer

logger = logging.getLogger(__name__)


async def text_message_handler(
    message: Message,
    dp: Dispatcher,
) -> None:
    """Handle incoming text messages.

    Processes user message through ProcessMessage use case and
    sends response back to user.

    Args:
        message: Incoming message object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    user = message.from_user
    user_text = message.text or ""

    if not user_text.strip():
        return

    logger.info(f"User {user.id} sent message: {user_text[:50]}...")

    # Get application container from dispatcher storage
    app_container: "ApplicationContainer" = dp.get("app_container")

    # Get or create user session
    try:
        session = await _get_or_create_session(
            telegram_id=user.id,
            unit_of_work=app_container.create_unit_of_work(),
            repo_factory=app_container.repository_factory,
        )
        logger.debug(f"Using session {session.session_id} for user {user.id}")
    except (RepositoryError, SessionNotFoundError) as e:
        logger.exception(f"Failed to get/create session for user {user.id}: {e}")
        await message.answer(
            "⚠️ Ошибка доступа к сессии. "
            "Пожалуйста, попробуйте позже."
        )
        return
    except Exception as e:
        logger.exception(f"Unexpected error getting session: {e}")
        await message.answer("⚠️ Произошла ошибка. Попробуйте позже.")
        return

    # Create controller and process message
    try:
        controller = MessageController(
            process_message=app_container.process_message,
            unit_of_work=app_container.create_unit_of_work(),
            repo_factory=app_container.repository_factory,
        )

        result = await controller.process_user_message(
            session_id=session.session_id,
            user_text=user_text,
        )

        await message.answer(result.response)
        logger.info(f"Sent response to user {user.id}")

    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке вашего сообщения. "
            "Пожалуйста, попробуйте позже."
        )


async def _get_or_create_session(
    telegram_id: int,
    unit_of_work: UnitOfWork,
    repo_factory: RepositoryFactory,
) -> Session:
    """Get existing session for user or create new one.

    Args:
        telegram_id: Telegram user ID.
        unit_of_work: Unit of work for transactional operations.
        repo_factory: Repository factory for creating repositories.

    Returns:
        Existing or newly created session.

    Raises:
        RepositoryError: If repository operation fails.
        SessionNotFoundError: If session not found after creation.
    """
    async with unit_of_work.transaction() as uow:
        repos = repo_factory.create_transactional_repos(uow.connection)

        # Try to get existing user
        user = await repos.user_repo.get_by_telegram_id(telegram_id)

        if user is None:
            # Create new user (user_id will be assigned by repository)
            user = User(
                telegram_id=telegram_id,
                default_mode=MemoryMode.SHORT_TERM,
            )
            await repos.user_repo.create(user)
            logger.debug(f"Created new user {telegram_id}")

            # Refresh user to get assigned ID
            user = await repos.user_repo.get_by_telegram_id(telegram_id)
            if user is None or user.user_id is None:
                raise RepositoryError("Failed to retrieve created user")

        # Get or create session for user using the new get_by_user_id method
        session = await repos.session_repo.get_by_user_id(user.user_id)

        if session is None:
            # Create new session (session_id will be assigned by repository)
            session = Session(
                user_id=user.user_id,
                memory_mode=user.default_mode,
            )
            await repos.session_repo.create(session)
            logger.debug(f"Created new session for user {user.user_id}")

            # Refresh session to get assigned ID
            session = await repos.session_repo.get_by_user_id(user.user_id)
            if session is None or session.session_id is None:
                raise SessionNotFoundError(user.user_id)
        else:
            # Update last activity
            session.last_activity = datetime.now(timezone.utc)
            await repos.session_repo.update_mode(
                session.session_id,
                session.memory_mode,
            )

        # At this point session and session_id are guaranteed to be set
        return session


def register_message_handlers(dp: Dispatcher) -> None:
    """Register text message handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    # Handle text messages (exclude commands)
    dp.message.register(text_message_handler, F.text)
    logger.debug("Message handlers registered")
