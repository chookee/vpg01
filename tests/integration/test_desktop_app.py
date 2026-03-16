"""Integration tests for desktop application components.

These tests verify integration between desktop UI components
and application use cases.
"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from datetime import datetime, timezone

# Skip all tests in this module if PyQt6 is not available
pytestmark = pytest.mark.skipif(
    "PyQt6" not in sys.modules,
    reason="PyQt6 not installed. Install with: pip install PyQt6>=6.6.0"
)


@pytest.fixture
def sample_message() -> Message:
    """Create a sample message for testing.
    
    Returns:
        Message instance with test data.
    """
    return Message(
        message_id=1,
        session_id=1,
        role="user",
        content="Test message content",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_app_container():
    """Create mock application container with use cases.
    
    Returns:
        MagicMock configured with async use case methods.
    """
    container = MagicMock()
    
    # Mock ProcessMessage
    process_result = MagicMock()
    process_result.response = "Test response"
    process_result.user_message = MagicMock(
        message_id=1,
        session_id=1,
        role="user",
        content="Hello",
    )
    process_result.assistant_message = MagicMock(
        message_id=2,
        session_id=1,
        role="assistant",
        content="Hi there",
    )
    container.process_message.execute = AsyncMock(return_value=process_result)
    
    # Mock ViewHistory
    container.view_history.execute = AsyncMock(return_value=[])
    
    # Mock EditMessage
    container.edit_message.execute = AsyncMock(return_value=MagicMock(
        message_id=1,
        session_id=1,
        role="user",
        content="Updated",
    ))
    
    # Mock DeleteMessage
    container.delete_message.execute = AsyncMock(return_value=None)
    
    # Mock ExportHistory
    container.export_history.execute = AsyncMock(return_value='{"version": "1.0"}')
    
    # Mock ImportHistory
    import_result = MagicMock()
    import_result.imported_count = 5
    import_result.skipped_count = 0
    import_result.errors = []
    import_result.__str__ = lambda self: "Imported: 5, Skipped: 0"
    container.import_history.execute = AsyncMock(return_value=import_result)
    
    return container


class TestDesktopAppIntegration:
    """Integration tests for desktop application."""

    @pytest.mark.asyncio
    async def test_message_controller_integration(
        self,
        mock_app_container,
    ) -> None:
        """Test MessageController integration with use case.
        
        Verifies that controller correctly:
        1. Calls use case with correct parameters
        2. Transforms result to ProcessMessageResult
        """
        from src.interfaces.desktop_app.controllers import MessageController
        
        controller = MessageController(
            process_message=mock_app_container.process_message
        )
        
        result = await controller.process_user_message(
            session_id=1,
            user_text="Hello",
        )
        
        # Verify use case was called
        mock_app_container.process_message.execute.assert_called_once_with(
            session_id=1,
            user_text="Hello",
        )
        
        # Verify result structure
        assert result.response == "Test response"
        assert result.user_message is not None
        assert result.assistant_message is not None

    @pytest.mark.asyncio
    async def test_history_controller_integration(
        self,
        mock_app_container,
    ) -> None:
        """Test HistoryController integration with use case.
        
        Verifies that controller correctly:
        1. Calls ViewHistory use case
        2. Returns message list
        """
        from src.interfaces.desktop_app.controllers import HistoryController
        
        # Setup mock to return test messages
        test_messages = [
            Message(
                message_id=1,
                session_id=1,
                role="user",
                content="Hello",
                timestamp=datetime.now(timezone.utc),
            ),
            Message(
                message_id=2,
                session_id=1,
                role="assistant",
                content="Hi",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        mock_app_container.view_history.execute = AsyncMock(
            return_value=test_messages
        )
        
        controller = HistoryController(
            view_history=mock_app_container.view_history
        )
        
        messages = await controller.get_history(session_id=1)
        
        # Verify use case was called
        mock_app_container.view_history.execute.assert_called_once_with(
            session_id=1
        )
        
        # Verify result
        assert len(messages) == 2
        assert messages[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_export_import_controller_integration(
        self,
        mock_app_container,
    ) -> None:
        """Test ExportImportController integration with use cases.
        
        Verifies that controller correctly:
        1. Calls ExportHistory use case
        2. Calls ImportHistory use case
        3. Transforms results appropriately
        """
        from src.interfaces.desktop_app.controllers import ExportImportController
        
        controller = ExportImportController(
            export_history=mock_app_container.export_history,
            import_history=mock_app_container.import_history,
        )
        
        # Test export
        json_data = await controller.export_history(session_id=1)
        
        mock_app_container.export_history.execute.assert_called_once_with(
            session_id=1
        )
        assert json_data == '{"version": "1.0"}'
        
        # Test import
        result = await controller.import_history(
            session_id=1,
            json_data='{"version": "1.0"}',
        )
        
        mock_app_container.import_history.execute.assert_called_once_with(
            session_id=1,
            json_data='{"version": "1.0"}',
        )
        assert "Imported: 5" in result


class TestHistoryWidgetIntegration:
    """Integration tests for HistoryWidget."""

    def test_history_widget_set_messages(
        self,
        sample_message: Message,
    ) -> None:
        """Test HistoryWidget displays messages correctly.
        
        Verifies that widget:
        1. Creates message bubbles for each message
        2. Stores references to bubbles
        """
        from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget
        from PyQt6.QtWidgets import QApplication
        import sys
        
        # Ensure QApplication exists
        if not QApplication.instance():
            QApplication(sys.argv)
        
        widget = HistoryWidget()
        
        # Set messages
        widget.set_messages([sample_message])
        
        # Verify message was added
        assert len(widget._messages) == 1
        assert sample_message.message_id in widget._messages
        
        # Verify bubble properties
        bubble = widget._messages[sample_message.message_id]
        assert bubble.message_id == sample_message.message_id
        assert bubble.content == sample_message.content

    def test_history_widget_add_message(
        self,
        sample_message: Message,
    ) -> None:
        """Test HistoryWidget add_message functionality.
        
        Verifies that widget:
        1. Adds single message to display
        2. Updates internal message dictionary
        """
        from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        widget = HistoryWidget()
        
        # Add message
        widget.add_message(sample_message)
        
        # Verify
        assert len(widget._messages) == 1
        assert sample_message.message_id in widget._messages

    def test_history_widget_remove_message(
        self,
        sample_message: Message,
    ) -> None:
        """Test HistoryWidget remove_message functionality.
        
        Verifies that widget:
        1. Removes message from display
        2. Cleans up internal dictionary
        """
        from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        widget = HistoryWidget()
        widget.set_messages([sample_message])
        
        # Verify added
        assert len(widget._messages) == 1
        
        # Remove message
        widget.remove_message(sample_message.message_id)
        
        # Verify removed
        assert len(widget._messages) == 0
        assert sample_message.message_id not in widget._messages

    def test_history_widget_update_message(
        self,
        sample_message: Message,
    ) -> None:
        """Test HistoryWidget update_message functionality.
        
        Verifies that widget:
        1. Updates existing message content
        2. Preserves message ID
        """
        from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        widget = HistoryWidget()
        widget.set_messages([sample_message])
        
        # Update message
        updated_message = Message(
            message_id=sample_message.message_id,
            session_id=sample_message.session_id,
            role=sample_message.role,
            content="Updated content",
            timestamp=sample_message.timestamp,
        )
        widget.update_message(updated_message)
        
        # Verify update
        bubble = widget._messages[sample_message.message_id]
        assert bubble.content == "Updated content"

    def test_history_widget_clear_messages(
        self,
        sample_message: Message,
    ) -> None:
        """Test HistoryWidget _clear_messages functionality.
        
        Verifies that widget:
        1. Removes all messages from display
        2. Clears internal dictionary
        """
        from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        widget = HistoryWidget()
        
        # Add multiple messages
        messages = [
            sample_message,
            Message(
                message_id=2,
                session_id=1,
                role="assistant",
                content="Second message",
                timestamp=datetime.now(timezone.utc),
            ),
        ]
        widget.set_messages(messages)
        
        # Verify added
        assert len(widget._messages) == 2
        
        # Clear messages
        widget.set_messages([])  # This calls _clear_messages internally
        
        # Verify cleared
        assert len(widget._messages) == 0


class TestMainWindowIntegration:
    """Integration tests for MainWindow."""

    def test_main_window_initialization(
        self,
        mock_app_container,
    ) -> None:
        """Test MainWindow initializes correctly.
        
        Verifies that window:
        1. Creates UI components
        2. Sets up controllers
        3. Has correct initial state
        """
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        with patch('src.interfaces.desktop_app.main_window.build_app') as mock_build:
            mock_build.return_value = mock_app_container
            
            from src.interfaces.desktop_app.main_window import MainWindow
            
            window = MainWindow(session_id=1)
            
            # Verify window created
            assert window.windowTitle() == "VPg01 Desktop"
            assert window._session_id == 1
            
            # Verify controllers initialized
            assert window._message_controller is not None
            assert window._history_controller is not None
            assert window._edit_controller is not None
            assert window._delete_controller is not None
            assert window._export_import_controller is not None

    def test_main_window_export_import_flags(
        self,
        mock_app_container,
    ) -> None:
        """Test MainWindow export/import in-progress flags.
        
        Verifies that window:
        1. Initializes flags to False
        2. Can track operation state
        """
        from PyQt6.QtWidgets import QApplication
        import sys
        
        if not QApplication.instance():
            QApplication(sys.argv)
        
        with patch('src.interfaces.desktop_app.main_window.build_app') as mock_build:
            mock_build.return_value = mock_app_container
            
            from src.interfaces.desktop_app.main_window import MainWindow
            
            window = MainWindow(session_id=1)
            
            # Verify flags initialized
            assert window._export_in_progress is False
            assert window._import_in_progress is False
