"""Mode selection handlers for Telegram bot.

This module handles memory mode selection commands:
- /mode - Show current mode and available options
- /mode no_memory - Set no memory mode
- /mode short - Set short-term memory mode
- /mode long - Set long-term memory mode
- /mode both - Set both memory modes

Example:
    >>> dp = Dispatcher()
    >>> register_mode_handlers(dp)
"""

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.types import CallbackQuery

from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.exceptions import RepositoryError
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

if TYPE_CHECKING:
    from src.main import ApplicationContainer

logger = logging.getLogger(__name__)

# Mode descriptions
MODE_DESCRIPTIONS = {
    MemoryMode.NO_MEMORY: (
        "🚫 <b>Без памяти</b>\n\n"
        "Каждое сообщение обрабатывается отдельно. "
        "Бот не помнит контекст предыдущих сообщений."
    ),
    MemoryMode.SHORT_TERM: (
        "⚡ <b>Краткосрочная память</b>\n\n"
        "Бот помнит контекст текущей сессии. "
        "История хранится в оперативной памяти."
    ),
    MemoryMode.LONG_TERM: (
        "💾 <b>Долгосрочная память</b>\n\n"
        "Бот помнит все сообщения в базе данных. "
        "История сохраняется между сессиями."
    ),
    MemoryMode.BOTH: (
        "🔄 <b>Оба режима</b>\n\n"
        "Бот использует и краткосрочную, и долгосрочную память. "
        "Максимальный контекст и сохранение истории."
    ),
}


async def mode_command_handler(message: Message, dp: Dispatcher) -> None:
    """Handle /mode command.

    Shows current mode and available options with inline keyboard.

    Args:
        message: Incoming message object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    from src.main import ApplicationContainer

    app_container: ApplicationContainer = dp.get("app_container")
    telegram_id = message.from_user.id

    # Get current session mode
    current_mode = await _get_user_session_mode(
        telegram_id=telegram_id,
        unit_of_work=app_container.create_unit_of_work(),
        repo_factory=app_container.repository_factory,
    )

    keyboard = _create_mode_keyboard(current_mode)

    await message.answer(
        f"📊 <b>Текущий режим:</b> {current_mode.value}\n\n"
        f"Выберите режим памяти:",
        reply_markup=keyboard,
    )


async def mode_callback_handler(callback: CallbackQuery, dp: Dispatcher) -> None:
    """Handle mode selection callback.

    Updates session memory mode based on user selection.

    Args:
        callback: Callback query object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    from src.main import ApplicationContainer

    app_container: ApplicationContainer = dp.get("app_container")
    telegram_id = callback.from_user.id

    # Extract mode from callback data (e.g., "mode_short_term")
    mode_name = callback.data.replace("mode_", "")

    try:
        mode = MemoryMode(mode_name)
    except ValueError:
        await callback.answer("❌ Неверный режим", show_alert=True)
        return

    # Update session mode
    success = await _update_user_session_mode(
        telegram_id=telegram_id,
        new_mode=mode,
        unit_of_work=app_container.create_unit_of_work(),
        repo_factory=app_container.repository_factory,
    )

    if success:
        description = MODE_DESCRIPTIONS[mode]
        await callback.message.edit_text(
            f"✅ <b>Режим изменён!</b>\n\n{description}",
            reply_markup=_create_mode_keyboard(mode),
        )
        await callback.answer()
        logger.info(f"User {telegram_id} changed mode to {mode.value}")
    else:
        await callback.answer(
            "❌ Не удалось изменить режим. Попробуйте позже.",
            show_alert=True,
        )


def _create_mode_keyboard(current_mode: MemoryMode) -> InlineKeyboardMarkup:
    """Create inline keyboard with mode options.

    Args:
        current_mode: Currently selected mode.

    Returns:
        InlineKeyboardMarkup with mode buttons.
    """
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current_mode == MemoryMode.NO_MEMORY else ''}Без памяти",
                callback_data="mode_no_memory",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current_mode == MemoryMode.SHORT_TERM else ''}Краткосрочная",
                callback_data="mode_short_term",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current_mode == MemoryMode.LONG_TERM else ''}Долгосрочная",
                callback_data="mode_long_term",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'✅ ' if current_mode == MemoryMode.BOTH else ''}Оба режима",
                callback_data="mode_both",
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _get_user_session_mode(
    telegram_id: int,
    unit_of_work: UnitOfWork,
    repo_factory: RepositoryFactory,
) -> MemoryMode:
    """Get current memory mode for user's session.

    Args:
        telegram_id: Telegram user ID.
        unit_of_work: Unit of work for transactional operations.
        repo_factory: Repository factory for creating repositories.

    Returns:
        Current memory mode. Defaults to SHORT_TERM if user/session not found.
    """
    async with unit_of_work.transaction() as uow:
        repos = repo_factory.create_transactional_repos(uow.connection)

        user = await repos.user_repo.get_by_telegram_id(telegram_id)
        if user is None or user.user_id is None:
            return MemoryMode.SHORT_TERM  # Default mode

        session = await repos.session_repo.get_by_user_id(user.user_id)
        if session is None or session.session_id is None:
            return MemoryMode.SHORT_TERM  # Default mode

        return session.memory_mode


async def _update_user_session_mode(
    telegram_id: int,
    new_mode: MemoryMode,
    unit_of_work: UnitOfWork,
    repo_factory: RepositoryFactory,
) -> bool:
    """Update memory mode for user's session.

    Args:
        telegram_id: Telegram user ID.
        new_mode: New memory mode to set.
        unit_of_work: Unit of work for transactional operations.
        repo_factory: Repository factory for creating repositories.

    Returns:
        True if mode was updated successfully.
    """
    try:
        async with unit_of_work.transaction() as uow:
            repos = repo_factory.create_transactional_repos(uow.connection)

            user = await repos.user_repo.get_by_telegram_id(telegram_id)
            if user is None:
                # Create new user with default session
                user = User(
                    telegram_id=telegram_id,
                    default_mode=new_mode,
                )
                await repos.user_repo.create(user)
                user = await repos.user_repo.get_by_telegram_id(telegram_id)
                if user is None or user.user_id is None:
                    logger.error(f"Failed to retrieve created user {telegram_id}")
                    return False

            session = await repos.session_repo.get_by_user_id(user.user_id)
            if session is None:
                # Create new session
                session = Session(
                    user_id=user.user_id,
                    memory_mode=new_mode,
                )
                await repos.session_repo.create(session)
                # Refresh to get assigned session_id
                session = await repos.session_repo.get_by_user_id(user.user_id)
                if session is None or session.session_id is None:
                    logger.error(f"Failed to retrieve created session for user {user.user_id}")
                    return False
            else:
                await repos.session_repo.update_mode(session.session_id, new_mode)

            return True

    except RepositoryError as e:
        logger.exception(f"Repository error updating mode: {e}")
        return False
    except Exception as e:
        logger.exception(f"Failed to update mode: {e}")
        return False


def register_mode_handlers(dp: Dispatcher) -> None:
    """Register mode selection handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    dp.message.register(mode_command_handler, Command("mode"))
    dp.callback_query.register(mode_callback_handler, F.data.startswith("mode_"))
    logger.debug("Mode handlers registered")
