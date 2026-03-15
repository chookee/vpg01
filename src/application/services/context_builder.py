"""Context Builder service for assembling conversation context.

This module provides the ContextBuilder service responsible for building
conversation context based on the session's memory mode. It abstracts
the complexity of fetching messages from multiple storage sources
(long-term database and short-term in-memory store).

Memory Modes:
    - NO_MEMORY: Returns empty context (stateless conversation).
    - SHORT_TERM: Returns messages from in-memory store only.
    - LONG_TERM: Returns messages from database repository only.
    - BOTH: Returns merged messages from both sources, sorted by timestamp.

Example:
    >>> builder = ContextBuilder(long_term_repo, short_term_store)
    >>> context = await builder.build_context(session_id=1, mode=MemoryMode.BOTH)
"""

from typing import List

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionStore,
)


class ContextBuilder:
    """Service for building conversation context based on memory mode.

    Assembles messages from long-term and/or short-term storage
    depending on the session's memory mode configuration.

    Memory modes behavior:
        - NO_MEMORY: Returns empty context (stateless conversation).
        - SHORT_TERM: Returns messages from in-memory store only.
        - LONG_TERM: Returns messages from database repository only.
        - BOTH: Returns merged messages from both sources, sorted by timestamp.
    """

    def __init__(
        self,
        long_term_repo: MessageRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize ContextBuilder with storage dependencies.

        Args:
            long_term_repo: Repository for long-term message storage.
            short_term_store: Store for short-term in-memory messages.
        """
        self._long_term_repo: MessageRepository = long_term_repo
        self._short_term_store: SessionStore = short_term_store

    async def build_context(
        self,
        session_id: int,
        mode: MemoryMode,
    ) -> List[Message]:
        """Build conversation context based on memory mode.

        Retrieves messages from appropriate storage sources depending
        on the specified memory mode and returns them for LLM context.

        Args:
            session_id: Session identifier to build context for.
            mode: Memory mode determining which storage to use.

        Returns:
            List of messages ordered by timestamp.
            Empty list for NO_MEMORY mode or if no messages exist.

        Raises:
            InvalidDataError: If session_id is not positive.
        """
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )

        if mode == MemoryMode.NO_MEMORY:
            return []

        if mode == MemoryMode.SHORT_TERM:
            return await self._get_short_term_messages(session_id)

        if mode == MemoryMode.LONG_TERM:
            return await self._get_long_term_messages(session_id)

        if mode == MemoryMode.BOTH:
            return await self._get_merged_messages(session_id)

        return []

    async def _get_short_term_messages(
        self,
        session_id: int,
    ) -> List[Message]:
        """Get messages from short-term in-memory store.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages from in-memory store.
        """
        return await self._short_term_store.get_messages(session_id)

    async def _get_long_term_messages(
        self,
        session_id: int,
    ) -> List[Message]:
        """Get messages from long-term database repository.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages from database.
        """
        return await self._long_term_repo.get_by_session(session_id)

    async def _get_merged_messages(
        self,
        session_id: int,
    ) -> List[Message]:
        """Get messages from both storage sources and merge them.

        Combines messages from short-term and long-term storage,
        removes duplicates by message_id, and sorts by timestamp.

        Args:
            session_id: Session identifier.

        Returns:
            Merged and sorted list of unique messages.
        """
        short_term_msgs: List[Message] = (
            await self._get_short_term_messages(session_id)
        )
        long_term_msgs: List[Message] = (
            await self._get_long_term_messages(session_id)
        )

        merged_dict: dict[int, Message] = {}

        for msg in long_term_msgs:
            merged_dict[msg.message_id] = msg

        for msg in short_term_msgs:
            merged_dict[msg.message_id] = msg

        merged_list: List[Message] = list(merged_dict.values())
        merged_list.sort(key=lambda m: m.timestamp)

        return merged_list
