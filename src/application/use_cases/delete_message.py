"""DeleteMessage use case for removing messages.

This use case deletes a message from both long-term (database)
and short-term (in-memory) storage to ensure consistency across
all storage layers.
"""

import logging

from src.domain.entities.message import Message
from src.domain.exceptions import InvalidDataError, MessageNotFoundError
from src.domain.interfaces.repositories import MessageRepository, SessionStore

logger = logging.getLogger(__name__)


class DeleteMessage:
    """Use case for deleting messages.

    Removes message from long-term storage (database) and
    short-term storage (in-memory) if it exists there.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize DeleteMessage use case.

        Args:
            message_repo: Repository for long-term message storage.
            short_term_store: Store for short-term in-memory messages.
        """
        self._message_repo = message_repo
        self._short_term_store = short_term_store

    async def execute(self, message_id: int) -> None:
        """Delete a message by ID.

        Args:
            message_id: Message identifier to delete.

        Raises:
            InvalidDataError: If message_id is not positive.
            MessageNotFoundError: If message does not exist.
        """
        self._validate_input(message_id)
        message = await self._get_message(message_id)
        await self._message_repo.delete(message_id)
        await self._delete_from_short_term(message_id, message.session_id)

    async def _delete_from_short_term(
        self, message_id: int, session_id: int
    ) -> None:
        """Delete message from short-term store if it exists there.

        Note:
            Short-term store is a cache; failures should not affect the
            primary database operation. However, to prevent data inconsistency,
            we invalidate the entire session cache on failure.

        Args:
            message_id: Message identifier to delete.
            session_id: Session identifier.
        """
        try:
            deleted = await self._short_term_store.delete_message(
                message_id, session_id
            )
            if deleted:
                logger.debug(
                    f"Message {message_id} deleted from short-term store"
                )
        except Exception as e:
            # Cache invalidation: remove entire session to prevent inconsistency
            logger.warning(
                f"Failed to delete message {message_id} from short-term store. "
                f"Invalidating session cache to prevent inconsistency: {e}"
            )
            try:
                # Remove the entire session from cache
                await self._short_term_store.clear_session(session_id)
                logger.debug(
                    f"Cache invalidated for session {session_id}"
                )
            except Exception as cleanup_error:
                logger.error(
                    f"Failed to invalidate cache for session {session_id}: {cleanup_error}"
                )
            # Don't raise — cache is best-effort

    def _validate_input(self, message_id: int) -> None:
        """Validate use case input parameters.

        Args:
            message_id: Message identifier to validate.

        Raises:
            InvalidDataError: If message_id is not positive.
        """
        if message_id <= 0:
            raise InvalidDataError(
                f"message_id must be positive, got {message_id}"
            )

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
