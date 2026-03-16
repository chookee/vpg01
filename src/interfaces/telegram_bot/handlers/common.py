"""Common handlers for Telegram bot.

This module handles basic bot commands:
- /start - Welcome message and bot introduction
- /help - Help information

Example:
    >>> dp = Dispatcher()
    >>> register_common_handlers(dp)
"""

import logging

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def start_command_handler(message: Message) -> None:
    """Handle /start command.

    Sends welcome message to user.

    Args:
        message: Incoming message object.
    """
    user = message.from_user
    logger.info(f"User {user.id} started bot")

    await message.answer(
        "👋 <b>Добро пожаловать в VPg01!</b>\n\n"
        "Я — умный ассистент с поддержкой разных режимов памяти.\n\n"
        "<b>Доступные команды:</b>\n"
        "• /mode — выбрать режим памяти\n"
        "• /history — посмотреть историю сообщений\n"
        "• /edit — отредактировать сообщение\n"
        "• /delete — удалить сообщение\n"
        "• /help — справка\n\n"
        "Просто отправьте мне сообщение, и я отвечу!"
    )


async def help_command_handler(message: Message) -> None:
    """Handle /help command.

    Sends help information to user.

    Args:
        message: Incoming message object.
    """
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "<b>Режимы памяти:</b>\n"
        "• /mode — выбрать режим памяти\n"
        "• /mode no_memory — без памяти (каждое сообщение отдельно)\n"
        "• /mode short — краткосрочная память (в сессии)\n"
        "• /mode long — долгосрочная память (в БД)\n"
        "• /mode both — оба режима одновременно\n\n"
        "<b>Управление историей:</b>\n"
        "• /history — показать последние сообщения\n"
        "• /export — выгрузить историю в JSON файл\n"
        "• /import — загрузить историю из JSON файла\n"
        "• /edit &lt;id&gt; &lt;текст&gt; — изменить сообщение\n"
        "• /delete &lt;id&gt; — удалить сообщение\n\n"
        "<b>Примеры:</b>\n"
        "• /edit 5 Привет, мир!\n"
        "• /delete 5"
    )


def register_common_handlers(dp: Dispatcher) -> None:
    """Register common command handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    dp.message.register(start_command_handler, Command("start"))
    dp.message.register(help_command_handler, Command("help"))
    logger.debug("Common handlers registered")
