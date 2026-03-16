"""ImportHistory use case for importing session history from JSON.

This use case imports messages from a JSON format and saves them
to the session, with integrity validation.

Example:
    >>> importer = ImportHistory(message_repo, session_repo, short_term_store)
    >>> result = await importer.execute(session_id=1, json_data=json_string)
"""

import json
from datetime import datetime, timezone
from typing import Any

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, SessionNotFoundError
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    SessionStore,
)


class ImportHistoryError(Exception):
    """Error raised when history import fails."""

    pass


class ImportHistoryResult:
    """Result of ImportHistory use case.

    Attributes:
        imported_count: Number of messages successfully imported.
        skipped_count: Number of messages skipped (duplicates).
        errors: List of error messages for failed imports.
    """

    def __init__(
        self,
        imported_count: int = 0,
        skipped_count: int = 0,
        errors: list[str] | None = None,
    ) -> None:
        self.imported_count = imported_count
        self.skipped_count = skipped_count
        self.errors = errors or []

    def __str__(self) -> str:
        """Return summary of import operation."""
        parts = [f"Imported: {self.imported_count}", f"Skipped: {self.skipped_count}"]
        if self.errors:
            parts.append(f"Errors: {len(self.errors)}")
        return ", ".join(parts)


class ImportHistory:
    """Use case for importing session message history from JSON.

    Imports messages from a JSON format, validates integrity,
    and saves to both long-term and short-term storage.
    """

    # Supported export version
    SUPPORTED_VERSIONS = {"1.0"}

    def __init__(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        short_term_store: SessionStore,
    ) -> None:
        """Initialize ImportHistory use case.

        Args:
            message_repo: Repository for long-term message storage.
            session_repo: Repository for session management.
            short_term_store: Store for short-term in-memory messages.
        """
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._short_term_store = short_term_store

    async def execute(
        self,
        session_id: int,
        json_data: str,
    ) -> ImportHistoryResult:
        """Import session history from JSON string.

        Args:
            session_id: Session identifier to import history into.
            json_data: JSON string containing exported history.

        Returns:
            ImportHistoryResult with import statistics.

        Raises:
            InvalidDataError: If session_id is not positive or JSON is invalid.
            SessionNotFoundError: If session does not exist.
            ImportHistoryError: If import process fails.
        """
        self._validate_input(session_id, json_data)
        await self._verify_session_exists(session_id)

        try:
            # Parse JSON data
            import_data = json.loads(json_data)

            # Validate export format
            self._validate_export_format(import_data)

            # Import messages
            return await self._import_messages(session_id, import_data)

        except json.JSONDecodeError as e:
            raise ImportHistoryError(f"Invalid JSON format: {e}") from e
        except ImportHistoryError:
            raise
        except Exception as e:
            raise ImportHistoryError(f"Failed to import history: {e}") from e

    def _validate_input(self, session_id: int, json_data: str) -> None:
        """Validate use case input parameters.

        Args:
            session_id: Session identifier to validate.
            json_data: JSON data to validate.

        Raises:
            InvalidDataError: If validation fails.
        """
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )
        if not json_data or not json_data.strip():
            raise InvalidDataError("json_data cannot be empty")

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

    def _validate_export_format(self, import_data: dict[str, Any]) -> None:
        """Validate exported data format.

        Args:
            import_data: Parsed JSON data.

        Raises:
            ImportHistoryError: If format is invalid or unsupported.
        """
        # Check version
        version = import_data.get("version")
        if version not in self.SUPPORTED_VERSIONS:
            raise ImportHistoryError(
                f"Unsupported export version: {version}. "
                f"Supported: {', '.join(self.SUPPORTED_VERSIONS)}"
            )

        # Check required fields
        if "session" not in import_data:
            raise ImportHistoryError("Missing 'session' field in export data")
        if "messages" not in import_data:
            raise ImportHistoryError("Missing 'messages' field in export data")

        # Validate messages is a list
        if not isinstance(import_data["messages"], list):
            raise ImportHistoryError("'messages' must be a list")

    async def _import_messages(
        self,
        session_id: int,
        import_data: dict[str, Any],
    ) -> ImportHistoryResult:
        """Import messages from export data.

        Args:
            session_id: Target session identifier.
            import_data: Parsed export data.

        Returns:
            ImportHistoryResult with import statistics.
        """
        result = ImportHistoryResult()
        messages_data = import_data.get("messages", [])

        # Get existing message IDs to avoid duplicates
        existing_messages = await self._message_repo.get_by_session(session_id)
        existing_ids = {msg.message_id for msg in existing_messages}

        for msg_data in messages_data:
            try:
                # Check for duplicate by original message_id
                original_id = msg_data.get("message_id")
                if original_id in existing_ids:
                    result.skipped_count += 1
                    continue

                # Create message entity
                message = self._create_message_from_data(session_id, msg_data)

                # Save to long-term storage
                await self._message_repo.add(message)
                result.imported_count += 1

                # Also save to short-term storage
                await self._short_term_store.add_message(
                    session_id=session_id,
                    message=message,
                )

            except Exception as e:
                error_msg = f"Failed to import message {msg_data.get('message_id', '?')}: {e}"
                result.errors.append(error_msg)

        return result

    def _create_message_from_data(
        self,
        session_id: int,
        msg_data: dict[str, Any],
    ) -> Message:
        """Create Message entity from import data.

        Args:
            session_id: Target session identifier (remapped).
            msg_data: Message data from export.

        Returns:
            Message entity ready for import.

        Raises:
            ImportHistoryError: If message data is invalid.
        """
        try:
            # Validate content
            content = msg_data.get("content", "")
            if not content or not content.strip():
                raise ImportHistoryError("Message content cannot be empty")
            
            # Import MAX_CONTENT_LENGTH from message module
            from src.domain.entities.message import MAX_CONTENT_LENGTH
            if len(content) > MAX_CONTENT_LENGTH:
                raise ImportHistoryError(
                    f"Content length ({len(content)}) exceeds maximum ({MAX_CONTENT_LENGTH})"
                )

            # Validate role
            role = msg_data.get("role", "user")
            if role not in ("user", "assistant"):
                raise ImportHistoryError(f"Invalid role: {role}")

            # Parse timestamp
            timestamp_str = msg_data.get("timestamp")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = datetime.now(timezone.utc)

            # Parse memory mode
            memory_mode_str = msg_data.get("memory_mode_at_time")
            memory_mode = None
            if memory_mode_str:
                try:
                    memory_mode = MemoryMode(memory_mode_str)
                except ValueError:
                    pass  # Use None if invalid

            # Create message with new ID (0 = new)
            return Message(
                message_id=0,  # Will be assigned by repository
                session_id=session_id,  # Use target session_id
                role=role,
                content=content,
                timestamp=timestamp,
                model_used=msg_data.get("model_used"),
                memory_mode_at_time=memory_mode,
            )

        except Exception as e:
            raise ImportHistoryError(f"Invalid message data: {e}") from e
