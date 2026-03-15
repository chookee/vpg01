"""EditMessage use case for modifying existing messages.

This use case updates message content in both long-term (database)
and short-term (in-memory) storage to ensure consistency across
all storage layers.
"""

import logging

from src.domain.entities.message import Message
from src.domain.exceptions import InvalidDataError, MessageNotFoundError
from src.domain.interfaces.repositories import MessageRepository, SessionStore

logger = logging.getLogger(__name__)


class EditMessage:
    """Use case for editing message content.

    Updates message text in long-term storage (database) and
    short-term storage (in-memory) if the message exists there.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize EditMessage use case.

        Args:
            message_repo: Repository for long-term message storage.
            short_term_store: Store for short-term in-memory messages.
        """
        self._message_repo = message_repo
        self._short_term_store = short_term_store

    async def execute(
        self,
        message_id: int,
        new_content: str,
    ) -> Message:
        """Edit message content.

        Args:
            message_id: Message identifier to edit.
            new_content: New text content for the message.

        Returns:
            Updated message entity.

        Raises:
            InvalidDataError: If message_id is not positive or
                new_content is empty.
            MessageNotFoundError: If message does not exist.
        """
        self._validate_input(message_id, new_content)

        existing_message = await self._get_message(message_id)

        updated_message = Message(
            message_id=existing_message.message_id,
            session_id=existing_message.session_id,
            role=existing_message.role,
            content=new_content,
            timestamp=existing_message.timestamp,
            model_used=existing_message.model_used,
            memory_mode_at_time=existing_message.memory_mode_at_time,
        )

        # Обновляем в БД
        await self._message_repo.update(updated_message)

        # Обновляем в short-term store (если сообщение там есть)
        await self._update_short_term(updated_message)

        return updated_message

    async def _update_short_term(self, message: Message) -> None:
        """Update message in short-term store if it exists there.

        Note:
            Short-term store is a cache; failures should not affect the
            primary database operation. However, to prevent data inconsistency,
            we invalidate the cache entry on failure.

        Args:
            message: Updated message entity.
        """
        try:
            updated = await self._short_term_store.update_message(message)
            if updated:
                logger.debug(
                    f"Message {message.message_id} updated in short-term store"
                )
        except Exception as e:
            # Cache invalidation: remove stale entry to prevent inconsistency
            logger.warning(
                f"Failed to update message {message.message_id} in short-term store. "
                f"Invalidating cache entry to prevent inconsistency: {e}"
            )
            try:
                # Remove the session from cache to avoid serving stale data
                await self._short_term_store.clear_session(message.session_id)
                logger.debug(
                    f"Cache invalidated for session {message.session_id}"
                )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to invalidate cache for session {message.session_id}: {cleanup_error}"
                )
            # Don't raise — cache is best-effort

    def _validate_input(
        self,
        message_id: int,
        new_content: str,
    ) -> None:
        """Validate use case input parameters.

        Args:
            message_id: Message identifier to validate.
            new_content: New content to validate.

        Raises:
            InvalidDataError: If validation fails.
        """
        if message_id <= 0:
            raise InvalidDataError(
                f"message_id must be positive, got {message_id}"
            )
        if not new_content or not new_content.strip():
            raise InvalidDataError("new_content cannot be empty")

    async def _get_message(self, message_id: int) -> Message:
        """Get message by ID from repository.

        Args:
            message_id: Message identifier.

        Returns:
            Message entity.

        Raises:
            MessageNotFoundError: If message does not exist.
        """
        message = await self._message_repo.get_by_id(message_id)
        if message is None:
            raise MessageNotFoundError(message_id)
        return message
