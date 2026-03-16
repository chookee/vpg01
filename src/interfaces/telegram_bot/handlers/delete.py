"""Delete message handlers for Telegram bot.

This module handles the /delete command to remove existing messages.
Command format: /delete <message_id>

Example:
    >>> dp = Dispatcher()
    >>> register_delete_handlers(dp)
"""

import logging
from typing import TYPE_CHECKING

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

if TYPE_CHECKING:
    from src.main import ApplicationContainer

logger = logging.getLogger(__name__)


async def delete_command_handler(message: Message, dp: Dispatcher) -> None:
    """Handle /delete command.

    Deletes a message by ID. Command format: /delete <message_id>

    Args:
        message: Incoming message object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    from src.main import ApplicationContainer

    app_container: ApplicationContainer = dp.get("app_container")
    telegram_id = message.from_user.id
    command_text = message.text or ""

    # Parse command arguments
    parts = command_text.split()

    if len(parts) != 2:
        await message.answer(
            "❌ <b>Неверный формат команды</b>\n\n"
            "Используйте: /delete &lt;message_id&gt;\n\n"
            "Пример: /delete 5"
        )
        return

    try:
        message_id = int(parts[1])
    except ValueError:
        await message.answer(
            "❌ <b>Неверный ID сообщения</b>\n\n"
            "ID должен быть числом. Пример: /delete 5"
        )
        return

    try:
        # Get session ID for user
        session_id = await _get_user_session_id(
            telegram_id=telegram_id,
            unit_of_work=app_container.create_unit_of_work(),
            repo_factory=app_container.repository_factory,
        )

        if session_id is None:
            await message.answer(
                "📭 У вас ещё нет активной сессии. "
                "Отправьте сообщение, чтобы начать диалог."
            )
            return

        # Verify message belongs to user's session
        message_valid = await _verify_message_ownership(
            message_id=message_id,
            session_id=session_id,
            unit_of_work=app_container.create_unit_of_work(),
            repo_factory=app_container.repository_factory,
        )

        if not message_valid:
            await message.answer(
                f"❌ <b>Сообщение #{message_id} не найдено</b>\n\n"
                "Убедитесь, что ID верный и сообщение принадлежит вам. "
                "Используйте /history для просмотра сообщений."
            )
            return

        # Delete message via use case
        await app_container.delete_message.execute(message_id=message_id)

        await message.answer(
            f"✅ <b>Сообщение #{message_id} удалено!</b>"
        )

        logger.info(f"User {telegram_id} deleted message {message_id}")

    except Exception as e:
        logger.exception(f"Error deleting message: {e}")
        error_message = str(e)
        if "not found" in error_message.lower():
            await message.answer(
                f"❌ <b>Сообщение #{message_id} не найдено</b>\n\n"
                "Проверьте ID или используйте /history для просмотра."
            )
        else:
            await message.answer(
                "⚠️ Произошла ошибка при удалении сообщения. "
                "Пожалуйста, попробуйте позже."
            )


async def _get_user_session_id(
    telegram_id: int,
    unit_of_work: UnitOfWork,
    repo_factory: RepositoryFactory,
) -> int | None:
    """Get session ID for Telegram user.

    Args:
        telegram_id: Telegram user ID.
        unit_of_work: Unit of work for transactional operations.
        repo_factory: Repository factory for creating repositories.

    Returns:
        Session ID or None if user/session not found.
    """
    async with unit_of_work.transaction() as uow:
        repos = repo_factory.create_transactional_repos(uow.connection)

        user = await repos.user_repo.get_by_telegram_id(telegram_id)
        if user is None or user.user_id is None:
            return None

        session = await repos.session_repo.get_by_user_id(user.user_id)
        if session is None or session.session_id is None:
            return None

        return session.session_id


async def _verify_message_ownership(
    message_id: int,
    session_id: int,
    unit_of_work: UnitOfWork,
    repo_factory: RepositoryFactory,
) -> bool:
    """Verify that message belongs to user's session.

    Args:
        message_id: Message ID to verify.
        session_id: User's session ID.
        unit_of_work: Unit of work for transactional operations.
        repo_factory: Repository factory for creating repositories.

    Returns:
        True if message belongs to user's session.
    """
    async with unit_of_work.transaction() as uow:
        repos = repo_factory.create_transactional_repos(uow.connection)

        message = await repos.message_repo.get_by_id(message_id)
        if message is None:
            return False

        return message.session_id == session_id


def register_delete_handlers(dp: Dispatcher) -> None:
    """Register delete message handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    dp.message.register(delete_command_handler, Command("delete"))
    logger.debug("Delete handlers registered")
