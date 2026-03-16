"""Export/Import handlers for Telegram bot.

This module handles history export/import commands:
- /export - Export session history to JSON file
- /import - Import session history from JSON file

Example:
    >>> dp = Dispatcher()
    >>> register_export_import_handlers(dp)
"""

import json
import logging
from io import BytesIO
from typing import TYPE_CHECKING

from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from aiogram.types import CallbackQuery

from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

if TYPE_CHECKING:
    from src.main import ApplicationContainer

logger = logging.getLogger(__name__)

# Maximum file size for import (5 MB)
MAX_IMPORT_FILE_SIZE = 5 * 1024 * 1024


async def export_command_handler(message: Message, dp: Dispatcher) -> None:
    """Handle /export command.

    Exports session history to a JSON file and sends it to the user.

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

        # Export history via use case
        export_history = app_container.export_history
        json_data = await export_history.execute(session_id=session_id)

        # Check if history is empty
        data = json.loads(json_data)
        message_count = data.get("message_count", 0)

        if message_count == 0:
            await message.answer(
                "📭 История сообщений пуста. "
                "Нечего экспортировать."
            )
            return

        # Create file and send
        file_name = f"history_session_{session_id}.json"
        file_bytes = json_data.encode("utf-8")
        file_io = BytesIO(file_bytes)
        file_io.seek(0)

        input_file = FSInputFile(
            file_or_path=file_io,
            filename=file_name,
        )

        await message.answer_document(
            document=input_file,
            caption=(
                f"📤 <b>История экспортирована</b>\n\n"
                f"Сообщений: {message_count}\n"
                f"Файл: {file_name}"
            ),
        )

        logger.info(f"User {telegram_id} exported history ({message_count} messages)")

    except Exception as e:
        logger.exception(f"Error exporting history: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при экспорте истории. "
            "Пожалуйста, попробуйте позже."
        )


async def import_command_handler(message: Message, dp: Dispatcher) -> None:
    """Handle /import command.

    Shows instructions for importing history from a JSON file.

    Args:
        message: Incoming message object.
        dp: Aiogram dispatcher with app_container in storage.
    """
    await message.answer(
        "📥 <b>Импорт истории</b>\n\n"
        "Чтобы импортировать историю, отправьте JSON-файл как документ.\n\n"
        "⚠️ <b>Важно:</b>\n"
        "• Файл должен быть в формате экспорта VPg01\n"
        "• Сообщения будут добавлены к текущей сессии\n"
        "• Дубликаты сообщений будут пропущены\n\n"
        "Просто прикрепите файл к следующему сообщению."
    )


async def document_message_handler(message: Message, dp: Dispatcher) -> None:
    """Handle document messages for import.

    Processes attached JSON files and imports history.

    Args:
        message: Incoming message with document.
        dp: Aiogram dispatcher with app_container in storage.
    """
    from src.main import ApplicationContainer

    app_container: ApplicationContainer = dp.get("app_container")
    telegram_id = message.from_user.id

    # Check if message has a document
    if not message.document:
        return

    # Check file extension
    if not message.document.file_name.endswith(".json"):
        return

    # Check file size
    if message.document.file_size > MAX_IMPORT_FILE_SIZE:
        await message.answer(
            "❌ <b>Файл слишком большой</b>\n\n"
            f"Максимальный размер: {MAX_IMPORT_FILE_SIZE // 1024 // 1024} MB"
        )
        return

    try:
        # Download file
        file = await dp.bot.get_file(message.document.file_id)
        file_bytes = await dp.bot.download_file(file.file_path)
        json_data = file_bytes.read().decode("utf-8")

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

        # Import history via use case
        import_history = app_container.import_history
        result = await import_history.execute(
            session_id=session_id,
            json_data=json_data,
        )

        # Format result message
        caption = (
            f"📥 <b>Импорт завершён</b>\n\n"
            f"✅ Импортировано: {result.imported_count}\n"
            f"⏭️ Пропущено: {result.skipped_count}"
        )

        if result.errors:
            caption += f"\n⚠️ Ошибок: {len(result.errors)}"
            logger.warning(f"Import errors for user {telegram_id}: {result.errors}")

        await message.answer(caption)
        logger.info(
            f"User {telegram_id} imported history: "
            f"{result.imported_count} messages, {result.skipped_count} skipped"
        )

    except Exception as e:
        logger.exception(f"Error importing history: {e}")
        error_message = str(e)
        if "Invalid JSON" in error_message or "JSONDecodeError" in error_message:
            await message.answer(
                "❌ <b>Неверный формат файла</b>\n\n"
                "Файл должен быть валидным JSON в формате экспорта VPg01."
            )
        elif "Unsupported export version" in error_message:
            await message.answer(
                "❌ <b>Неподдерживаемая версия экспорта</b>\n\n"
                "Файл был создан в другой версии приложения."
            )
        else:
            await message.answer(
                "⚠️ Произошла ошибка при импорте истории. "
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


def register_export_import_handlers(dp: Dispatcher) -> None:
    """Register export/import handlers.

    Args:
        dp: Aiogram dispatcher instance.
    """
    dp.message.register(export_command_handler, Command("export"))
    dp.message.register(import_command_handler, Command("import"))
    dp.message.register(document_message_handler, F.document)
    logger.debug("Export/Import handlers registered")
