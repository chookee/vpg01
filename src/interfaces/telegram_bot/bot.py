"""Telegram bot runner.

This module provides the bot runner that initializes aiogram dispatcher,
registers all handlers, and starts polling.

Example:
    >>> from src.main import build_app
    >>> from src.infrastructure.config import get_settings
    >>> settings = get_settings()
    >>> app_container = build_app()
    >>> await run_bot(settings.telegram_bot_token, app_container)
"""

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from src.infrastructure.config import Settings

from .handlers.common import register_common_handlers
from .handlers.delete import register_delete_handlers
from .handlers.edit import register_edit_handlers
from .handlers.export_import import register_export_import_handlers
from .handlers.history import register_history_handlers
from .handlers.messages import register_message_handlers
from .handlers.mode import register_mode_handlers

logger = logging.getLogger(__name__)


async def run_bot(token: str, app_container: object) -> None:
    """Run Telegram bot with polling.

    Initializes bot, registers all handlers, and starts polling loop.

    Args:
        token: Telegram bot token from settings.
        app_container: Application container with use cases and services.

    Note:
        This function blocks until bot is stopped (Ctrl+C).
    """
    logger.info("Starting Telegram bot...")

    # Create bot and dispatcher
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Store application container in dispatcher storage
    # This makes it available to all handlers via callback_data
    dp["app_container"] = app_container

    # Register all handlers
    register_common_handlers(dp)
    register_message_handlers(dp)
    register_mode_handlers(dp)
    register_history_handlers(dp)
    register_export_import_handlers(dp)
    register_edit_handlers(dp)
    register_delete_handlers(dp)

    logger.info("Bot handlers registered, starting polling...")

    try:
        # Start polling
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")
