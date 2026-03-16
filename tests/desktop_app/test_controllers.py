"""Tests for desktop application controllers.

These tests verify that desktop controllers correctly delegate
to application use cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.process_message import (
    ProcessMessage,
    ProcessMessageResult,
)
from src.application.use_cases.view_history import ViewHistory
from src.application.use_cases.edit_message import EditMessage
from src.application.use_cases.delete_message import DeleteMessage
from src.application.use_cases.export_history import ExportHistory
from src.application.use_cases.import_history import ImportHistory
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.interfaces.desktop_app.controllers import (
    MessageController,
    HistoryController,
    EditMessageController,
    DeleteMessageController,
    ExportImportController,
)


@pytest.fixture
def sample_message():
    """Create a sample message entity."""
    from datetime import datetime, timezone

    return Message(
        message_id=1,
        session_id=1,
        role="user",
        content="Test message",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_process_message():
    """Create a mock ProcessMessage use case."""
    mock = AsyncMock(spec=ProcessMessage)
    mock.execute = AsyncMock(return_value=ProcessMessageResult(
        response="Test response",
        user_message=MagicMock(message_id=1, session_id=1, role="user", content="Hello"),
        assistant_message=MagicMock(message_id=2, session_id=1, role="assistant", content="Hi"),
    ))
    return mock


@pytest.fixture
def mock_view_history():
    """Create a mock ViewHistory use case."""
    mock = AsyncMock(spec=ViewHistory)
    mock.execute = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_edit_message():
    """Create a mock EditMessage use case."""
    mock = AsyncMock(spec=EditMessage)
    mock.execute = AsyncMock(return_value=MagicMock(
        message_id=1,
        session_id=1,
        role="user",
        content="Updated content",
    ))
    return mock


@pytest.fixture
def mock_delete_message():
    """Create a mock DeleteMessage use case."""
    mock = AsyncMock(spec=DeleteMessage)
    mock.execute = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_export_history():
    """Create a mock ExportHistory use case."""
    mock = AsyncMock(spec=ExportHistory)
    mock.execute = AsyncMock(return_value='{"version": "1.0", "messages": []}')
    return mock


@pytest.fixture
def mock_import_history():
    """Create a mock ImportHistory use case."""
    mock = AsyncMock(spec=ImportHistory)
    result = MagicMock()
    result.imported_count = 5
    result.skipped_count = 0
    result.errors = []
    result.__str__ = lambda self: "Imported: 5, Skipped: 0"
    mock.execute = AsyncMock(return_value=result)
    return mock


class TestMessageController:
    """Tests for MessageController."""

    @pytest.mark.asyncio
    async def test_process_user_message(self, mock_process_message):
        """Test processing a user message."""
        controller = MessageController(process_message=mock_process_message)

        result = await controller.process_user_message(
            session_id=1,
            user_text="Hello",
            mode=MemoryMode.LONG_TERM,
        )

        assert result.response == "Test response"
        mock_process_message.execute.assert_called_once_with(
            session_id=1,
            user_text="Hello",
            mode=MemoryMode.LONG_TERM,
        )

    @pytest.mark.asyncio
    async def test_process_user_message_without_mode(self, mock_process_message):
        """Test processing a user message without mode (uses session's mode)."""
        controller = MessageController(process_message=mock_process_message)

        result = await controller.process_user_message(
            session_id=1,
            user_text="Hello",
        )

        assert result.response == "Test response"
        mock_process_message.execute.assert_called_once_with(
            session_id=1,
            user_text="Hello",
            mode=None,
        )


class TestHistoryController:
    """Tests for HistoryController."""

    @pytest.mark.asyncio
    async def test_get_history(self, mock_view_history):
        """Test getting session history."""
        controller = HistoryController(view_history=mock_view_history)

        messages = await controller.get_history(session_id=1)

        assert messages == []
        mock_view_history.execute.assert_called_once_with(session_id=1)


class TestEditMessageController:
    """Tests for EditMessageController."""

    @pytest.mark.asyncio
    async def test_edit_message(self, mock_edit_message):
        """Test editing a message."""
        controller = EditMessageController(edit_message=mock_edit_message)

        result = await controller.edit_message(
            message_id=1,
            new_content="Updated content",
        )

        assert result.content == "Updated content"
        mock_edit_message.execute.assert_called_once_with(
            message_id=1,
            new_content="Updated content",
        )


class TestDeleteMessageController:
    """Tests for DeleteMessageController."""

    @pytest.mark.asyncio
    async def test_delete_message(self, mock_delete_message):
        """Test deleting a message."""
        controller = DeleteMessageController(delete_message=mock_delete_message)

        await controller.delete_message(message_id=1)

        mock_delete_message.execute.assert_called_once_with(message_id=1)


class TestExportImportController:
    """Tests for ExportImportController."""

    @pytest.mark.asyncio
    async def test_export_history(self, mock_export_history):
        """Test exporting session history."""
        controller = ExportImportController(
            export_history=mock_export_history,
            import_history=MagicMock(),
        )

        json_data = await controller.export_history(session_id=1)

        assert json_data == '{"version": "1.0", "messages": []}'
        mock_export_history.execute.assert_called_once_with(session_id=1)

    @pytest.mark.asyncio
    async def test_import_history(self, mock_import_history):
        """Test importing session history."""
        controller = ExportImportController(
            export_history=MagicMock(),
            import_history=mock_import_history,
        )

        result = await controller.import_history(
            session_id=1,
            json_data='{"version": "1.0"}',
        )

        assert "Imported: 5" in result
        mock_import_history.execute.assert_called_once_with(
            session_id=1,
            json_data='{"version": "1.0"}',
        )
