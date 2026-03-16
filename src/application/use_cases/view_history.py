"""ViewHistory use case for retrieving session message history.

This use case retrieves all messages for a session from both
long-term and short-term storage, merges them, removes duplicates,
and returns them sorted by timestamp.
"""

from typing import List

from src.domain.entities.message import Message
from src.domain.exceptions import InvalidDataError, SessionNotFoundError
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    SessionStore,
)


class ViewHistory:
    """Use case for viewing session message history.

    Retrieves messages from both long-term (database) and short-term
    (in-memory) storage, merges them by message_id, and returns
    chronologically sorted list.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize ViewHistory use case.

        Args:
            message_repo: Repository for long-term message storage.
            session_repo: Repository for session management.
            short_term_store: Store for short-term in-memory messages.
        """
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._short_term_store = short_term_store

    async def execute(self, session_id: int) -> List[Message]:
        """Retrieve all messages for a session.

        Args:
            session_id: Session identifier to get history for.

        Returns:
            List of messages sorted by timestamp (oldest first).
            Empty list if session has no messages.

        Raises:
            InvalidDataError: If session_id is not positive.
            SessionNotFoundError: If session does not exist.
        """
        self._validate_input(session_id)
        await self._verify_session_exists(session_id)

        # Получаем сообщения из обоих хранилищ
        long_term_msgs = await self._message_repo.get_by_session(session_id)
        short_term_msgs = await self._short_term_store.get_messages(session_id)

        # Объединяем с удалением дубликатов по message_id
        merged_dict: dict[int, Message] = {}
        for msg in long_term_msgs:
            merged_dict[msg.message_id] = msg
        for msg in short_term_msgs:
            merged_dict[msg.message_id] = msg

        # Сортируем по timestamp, затем по message_id для детерминированного порядка
        merged_list = list(merged_dict.values())
        merged_list.sort(key=lambda m: (m.timestamp, m.message_id))

        return merged_list

    def _validate_input(self, session_id: int) -> None:
        """Validate use case input parameters.

        Args:
            session_id: Session identifier to validate.

        Raises:
            InvalidDataError: If session_id is not positive.
        """
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )

    async def _verify_session_exists(self, session_id: int) -> None:
        """Verify that session exists.

        Args:
            session_id: Session identifier to check.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self._session_repo.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
