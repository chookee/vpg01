"""History view handlers for Telegram bot.

This module handles the /history command to display session message history.

Example:
    >>> dp = Dispatcher()
    >>> register_history_handlers(dp)
"""

import logging
from typing import TYPE_CHECKING

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from src.domain.entities.message import Message
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

if TYPE_CHECKING:
    from src.main import ApplicationContainer

logger = logging.getLogger(__name__)

# Maximum messages to show in history
MAX_HISTORY_MESSAGES = 20


async def history_command_handler(message: Message, dp: Dispatcher) -> None:
    """Handle /history command.

    Displays recent messages from the user's session.

    Args:
        message: Incoming message object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    from src.main import ApplicationContainer

    app_container: ApplicationContainer = dp.get("app_container")
    telegram_id = message.from_user.id

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

        # Get history via use case
        history = await app_container.view_history.execute(session_id=session_id)

        if not history:
            await message.answer(
                "📭 История сообщений пуста. "
                "Отправьте сообщение, чтобы начать диалог."
            )
            return

        # Format and send history
        formatted_history = _format_history(history, MAX_HISTORY_MESSAGES)
        await message.answer(formatted_history)

        logger.info(f"User {telegram_id} viewed history ({len(history)} messages)")

    except Exception as e:
        logger.exception(f"Error retrieving history: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при загрузке истории. "
            "Пожалуйста, попробуйте позже."
        )


def _format_history(messages: list[Message], limit: int) -> str:
    """Format message history for display.

    Args:
        messages: List of messages to format.
        limit: Maximum number of messages to show.

    Returns:
        Formatted history string.
    """
    # Get last N messages
    recent_messages = messages[-limit:] if len(messages) > limit else messages

    lines = [f"📜 <b>История сообщений</b> ({len(recent_messages)} из {len(messages)}):\n"]

    for msg in recent_messages:
        # Format timestamp
        timestamp = msg.timestamp.strftime("%d.%m.%Y %H:%M")

        # Format role
        role_icon = "👤" if msg.role == "user" else "🤖"
        role_name = "Вы" if msg.role == "user" else "Бот"

        # Truncate long messages
        content = msg.content
        if len(content) > 500:
            content = content[:497] + "..."

        lines.append(f"\n{role_icon} <b>{role_name}</b> ({timestamp}):")
        lines.append(f"<i>{content}</i>")

    return "\n".join(lines)


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


def register_history_handlers(dp: Dispatcher) -> None:
    """Register history view handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    dp.message.register(history_command_handler, Command("history"))
    logger.debug("History handlers registered")
