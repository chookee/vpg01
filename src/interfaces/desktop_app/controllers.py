"""Desktop application controllers.

This module provides controllers for the desktop application,
bridging UI with application use cases.
"""

import logging
from dataclasses import dataclass

from src.application.use_cases.delete_message import DeleteMessage
from src.application.use_cases.edit_message import EditMessage
from src.application.use_cases.export_history import ExportHistory
from src.application.use_cases.import_history import ImportHistory
from src.application.use_cases.process_message import ProcessMessage
from src.application.use_cases.view_history import ViewHistory
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode

logger = logging.getLogger(__name__)


@dataclass
class ProcessMessageResult:
    """Result of processing a user message.

    Attributes:
        response: Generated response text.
        user_message: Saved user message entity.
        assistant_message: Saved assistant message entity.
    """

    response: str
    user_message: Message
    assistant_message: Message


class MessageController:
    """Controller for processing user messages."""

    def __init__(
        self,
        process_message: ProcessMessage,
    ) -> None:
        """Initialize MessageController.

        Args:
            process_message: ProcessMessage use case instance.
        """
        self._process_message = process_message

    async def process_user_message(
        self,
        session_id: int,
        user_text: str,
        mode: MemoryMode | None = None,
    ) -> ProcessMessageResult:
        """Process a user message and return the response.

        Args:
            session_id: Session identifier.
            user_text: User message text.
            mode: Optional memory mode override. If None, uses session's mode.

        Returns:
            ProcessMessageResult with response and messages.
        """
        logger.debug(
            f"Processing message for session {session_id}: {user_text[:50]}..., mode={mode}"
        )

        result = await self._process_message.execute(
            session_id=session_id,
            user_text=user_text,
            mode=mode,
        )

        logger.info(
            f"Message processed for session {session_id}, "
            f"response length: {len(result.response)}"
        )
        logger.debug(f"Assistant response: {result.response}")

        return ProcessMessageResult(
            response=result.response,
            user_message=result.user_message,
            assistant_message=result.assistant_message,
        )


class HistoryController:
    """Controller for viewing session history."""

    def __init__(
        self,
        view_history: ViewHistory,
    ) -> None:
        """Initialize HistoryController.

        Args:
            view_history: ViewHistory use case instance.
        """
        self._view_history = view_history

    async def get_history(self, session_id: int) -> list[Message]:
        """Get session history.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages sorted by timestamp.
        """
        return await self._view_history.execute(session_id=session_id)


class EditMessageController:
    """Controller for editing messages."""

    def __init__(
        self,
        edit_message: EditMessage,
    ) -> None:
        """Initialize EditMessageController.

        Args:
            edit_message: EditMessage use case instance.
        """
        self._edit_message = edit_message

    async def edit_message(
        self,
        message_id: int,
        new_content: str,
    ) -> Message:
        """Edit a message.

        Args:
            message_id: Message identifier.
            new_content: New message content.

        Returns:
            Updated message entity.
        """
        logger.debug(f"Editing message {message_id}")
        
        result = await self._edit_message.execute(
            message_id=message_id,
            new_content=new_content,
        )
        
        logger.info(f"Message {message_id} edited successfully")
        
        return result


class DeleteMessageController:
    """Controller for deleting messages."""

    def __init__(
        self,
        delete_message: DeleteMessage,
    ) -> None:
        """Initialize DeleteMessageController.

        Args:
            delete_message: DeleteMessage use case instance.
        """
        self._delete_message = delete_message

    async def delete_message(self, message_id: int) -> None:
        """Delete a message.

        Args:
            message_id: Message identifier to delete.
        """
        logger.debug(f"Deleting message {message_id}")
        await self._delete_message.execute(message_id=message_id)
        logger.info(f"Message {message_id} deleted successfully")


class ExportImportController:
    """Controller for export/import operations."""

    def __init__(
        self,
        export_history: ExportHistory,
        import_history: ImportHistory,
    ) -> None:
        """Initialize ExportImportController.

        Args:
            export_history: ExportHistory use case instance.
            import_history: ImportHistory use case instance.
        """
        self._export_history = export_history
        self._import_history = import_history

    async def export_history(self, session_id: int) -> str:
        """Export session history to JSON.

        Args:
            session_id: Session identifier.

        Returns:
            JSON string with session history.
        """
        logger.debug(f"Exporting history for session {session_id}")
        result = await self._export_history.execute(session_id=session_id)
        logger.info(f"History exported for session {session_id} ({len(result)} bytes)")
        return result

    async def import_history(
        self,
        session_id: int,
        json_data: str,
    ) -> str:
        """Import session history from JSON.

        Args:
            session_id: Session identifier.
            json_data: JSON string with exported history.

        Returns:
            Import result summary string.
        """
        logger.debug(f"Importing history for session {session_id}")
        result = await self._import_history.execute(
            session_id=session_id,
            json_data=json_data,
        )
        result_str = str(result)
        logger.info(f"History imported for session {session_id}: {result_str}")
        return result_str
