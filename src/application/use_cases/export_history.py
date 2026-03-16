"""ExportHistory use case for exporting session history to JSON.

This use case exports all messages from a session to a JSON format
that can be saved to a file or sent to the user.

Example:
    >>> exporter = ExportHistory(message_repo, session_repo, short_term_store)
    >>> json_data = await exporter.execute(session_id=1)
"""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from src.domain.entities.message import Message
from src.domain.exceptions import InvalidDataError, SessionNotFoundError
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    SessionStore,
)


class ExportHistoryError(Exception):
    """Error raised when history export fails."""

    pass


class ExportHistory:
    """Use case for exporting session message history to JSON.

    Exports messages from both long-term (database) and short-term
    (in-memory) storage to a JSON format with metadata.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize ExportHistory use case.

        Args:
            message_repo: Repository for long-term message storage.
            session_repo: Repository for session management.
            short_term_store: Store for short-term in-memory messages.
        """
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._short_term_store = short_term_store

    async def execute(self, session_id: int) -> str:
        """Export session history to JSON string.

        Args:
            session_id: Session identifier to export history for.

        Returns:
            JSON string containing session history with metadata.

        Raises:
            InvalidDataError: If session_id is not positive.
            SessionNotFoundError: If session does not exist.
            ExportHistoryError: If export process fails.
        """
        self._validate_input(session_id)
        session = await self._verify_session_exists(session_id)

        try:
            # Get all messages (merged from both stores)
            messages = await self._get_all_messages(session_id)

            # Build export data structure
            export_data = self._build_export_data(session_id, session, messages)

            # Convert to JSON with proper datetime handling
            return json.dumps(export_data, ensure_ascii=False, indent=2, default=str)

        except json.JSONEncodeError as e:
            raise ExportHistoryError(f"Failed to encode history to JSON: {e}") from e
        except Exception as e:
            raise ExportHistoryError(f"Failed to export history: {e}") from e

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

    async def _verify_session_exists(self, session_id: int) -> Any:
        """Verify that session exists and return it.

        Args:
            session_id: Session identifier to check.

        Returns:
            Session entity.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self._session_repo.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    async def _get_all_messages(self, session_id: int) -> list[Message]:
        """Get all messages from both storage sources.

        Args:
            session_id: Session identifier.

        Returns:
            List of messages merged and sorted by timestamp.
        """
        # Get messages from both stores
        long_term_msgs = await self._message_repo.get_by_session(session_id)
        short_term_msgs = await self._short_term_store.get_messages(session_id)

        # Merge by message_id to remove duplicates
        merged_dict: dict[int, Message] = {}
        for msg in long_term_msgs:
            merged_dict[msg.message_id] = msg
        for msg in short_term_msgs:
            merged_dict[msg.message_id] = msg

        # Sort by timestamp, then by message_id for deterministic order
        merged_list = list(merged_dict.values())
        merged_list.sort(key=lambda m: (m.timestamp, m.message_id))

        return merged_list

    def _build_export_data(
        self,
        session_id: int,
        session: Any,
        messages: list[Message],
    ) -> dict[str, Any]:
        """Build export data structure with metadata.

        Args:
            session_id: Session identifier.
            session: Session entity.
            messages: List of messages to export.

        Returns:
            Dictionary containing export metadata and messages.
        """
        return {
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session": {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "memory_mode": session.memory_mode.value,
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
            },
            "message_count": len(messages),
            "messages": [
                {
                    "message_id": msg.message_id,
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "model_used": msg.model_used,
                    "memory_mode_at_time": (
                        msg.memory_mode_at_time.value
                        if msg.memory_mode_at_time
                        else None
                    ),
                }
                for msg in messages
            ],
        }
