"""History widget for displaying chat messages.

This module provides a custom widget for displaying chat message history
with support for:
- Message bubbles with role-based styling
- Context menu for edit/delete operations
- Auto-scroll to bottom on new messages
"""

import itertools
import logging
from typing import Optional

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QAction, QPalette, QColor
from PyQt6.QtWidgets import (
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QLabel,
    QFrame,
)

from src.domain.entities.message import Message

logger = logging.getLogger(__name__)


class MessageBubble(QFrame):
    """Widget representing a single message bubble.

    Signals:
        edit_requested: Emitted when edit is requested (message_id, content).
        delete_requested: Emitted when delete is requested (message_id).

    Attributes:
        message_id: Message identifier.
    """

    edit_requested = pyqtSignal(int, str)
    delete_requested = pyqtSignal(int)

    def __init__(
        self,
        message: Message,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialize MessageBubble.

        Args:
            message: Message entity to display.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._message = message

        self._setup_ui()
        self._setup_context_menu()

    @property
    def message_id(self) -> int:
        """Get message ID."""
        return self._message.message_id

    @property
    def content(self) -> str:
        """Get message content."""
        return self._message.content

    def _setup_ui(self) -> None:
        """Set up the message bubble UI."""
        # Frame styling
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Role label
        role_text = "Пользователь" if self._message.role == "user" else "Ассистент"
        self._role_label = QLabel(f"<b>{role_text}</b>")
        layout.addWidget(self._role_label)

        # Content label with word wrap
        self._content_label = QLabel(self._message.content)
        self._content_label.setWordWrap(True)
        self._content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self._content_label)

        # Timestamp label
        timestamp_str = self._message.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self._timestamp_label = QLabel(f"<i>{timestamp_str}</i>")
        self._timestamp_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._timestamp_label)

        # Apply role-based styling
        self._apply_styling()

    def _apply_styling(self) -> None:
        """Apply role-based styling to the bubble."""
        palette = self.palette()

        if self._message.role == "user":
            # User messages: light blue background
            self.setAutoFillBackground(True)
            palette.setColor(
                QPalette.ColorRole.Window,
                QColor(220, 240, 255),
            )
            palette.setColor(
                QPalette.ColorRole.WindowText,
                QColor(0, 0, 0),
            )
        else:
            # Assistant messages: light gray background
            self.setAutoFillBackground(True)
            palette.setColor(
                QPalette.ColorRole.Window,
                QColor(240, 240, 240),
            )
            palette.setColor(
                QPalette.ColorRole.WindowText,
                QColor(0, 0, 0),
            )

        self.setPalette(palette)

    def _setup_context_menu(self) -> None:
        """Set up the context menu for edit/delete."""
        # Context menu is created on-demand in _show_context_menu

    def _show_context_menu(self, position) -> None:
        """Show context menu at the given position.

        Creates and displays a context menu with Edit and Delete actions.
        The menu is positioned at the cursor location relative to the widget.

        Args:
            position: Local position within the widget where the menu
                should be shown (typically from customContextMenuRequested).
        """
        menu = QMenu(self)

        # Edit action
        edit_action = QAction("Редактировать", self)
        edit_action.triggered.connect(self._on_edit_triggered)
        menu.addAction(edit_action)

        # Delete action
        delete_action = QAction("Удалить", self)
        delete_action.triggered.connect(self._on_delete_triggered)
        menu.addAction(delete_action)

        # Show menu
        menu.exec(self.mapToGlobal(position))

    def _on_edit_triggered(self) -> None:
        """Handle edit action triggered from context menu.

        Emits edit_requested signal with message ID and content.
        The parent widget should connect to this signal to handle
        the actual editing logic.
        """
        self.edit_requested.emit(self._message.message_id, self._message.content)

    def _on_delete_triggered(self) -> None:
        """Handle delete action triggered from context menu.

        Emits delete_requested signal with message ID.
        The parent widget should connect to this signal to handle
        the actual deletion logic.
        """
        self.delete_requested.emit(self._message.message_id)

    def update_content(self, new_content: str) -> None:
        """Update message content.

        Updates the displayed content label and creates a new Message
        entity with the updated content while preserving all other fields.

        Args:
            new_content: New message content to display.
        """
        self._content_label.setText(new_content)
        self._message = Message(
            message_id=self._message.message_id,
            session_id=self._message.session_id,
            role=self._message.role,
            content=new_content,
            timestamp=self._message.timestamp,
            model_used=self._message.model_used,
            memory_mode_at_time=self._message.memory_mode_at_time,
        )


class HistoryWidget(QWidget):
    """Widget for displaying chat message history.

    This widget manages a scrollable list of message bubbles with:
    - Role-based styling (user vs assistant)
    - Context menu for each message (edit/delete)
    - Auto-scroll to bottom on new messages
    - Dynamic message addition/removal/update

    Signals:
        message_edit_requested: Emitted when edit is requested (message_id, content).
        message_delete_requested: Emitted when delete is requested (message_id).

    Example:
        >>> widget = HistoryWidget()
        >>> widget.message_edit_requested.connect(on_edit)
        >>> widget.message_delete_requested.connect(on_delete)
        >>> widget.set_messages(messages)
    """

    message_edit_requested = pyqtSignal(int, str)
    message_delete_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize HistoryWidget.

        Args:
            parent: Parent widget for proper Qt parent-child hierarchy.
        """
        super().__init__(parent)

        self._messages: dict[int, MessageBubble] = {}
        self._scroll_pending = False  # Protect against race conditions
        # Counter for generating unique keys for unsaved messages (message_id=0)
        # This prevents collision when multiple unsaved messages are added
        self._unsaved_counter = itertools.count(-1, -1)  # -1, -2, -3, ...
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the history widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Scroll area for messages
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        # Container widget for messages
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(5, 5, 5, 5)
        self._container_layout.setSpacing(5)
        self._container_layout.addStretch()

        self._scroll_area.setWidget(self._container)
        layout.addWidget(self._scroll_area)

    def set_messages(self, messages: list[Message]) -> None:
        """Set all messages to display.

        Clears existing messages and adds the provided ones.
        Scrolls to bottom after all messages are added.

        Args:
            messages: List of message entities to display.
                Sorted by timestamp for correct chronological order.
        """
        # Clear existing
        self._clear_messages()

        # Add new messages
        for message in messages:
            self._add_message_internal(message)

        # Scroll to bottom immediately
        self._scroll_to_bottom()
        
        # Force another scroll after layout update (for large message lists)
        QTimer.singleShot(200, self._do_scroll_to_bottom)

    def add_message(self, message: Message) -> None:
        """Add a single message to the history.

        Creates a new message bubble and appends it to the scroll area.
        Automatically scrolls to bottom to show the new message.

        Args:
            message: Message entity to add.
        """
        self._add_message_internal(message)
        self._scroll_to_bottom()

    def update_message(self, message: Message) -> None:
        """Update an existing message.

        Finds the message bubble by ID and updates its content.
        If message is not found, logs a warning.

        Args:
            message: Updated message entity with new content.
        """
        # Search for message by ID (handles both positive and negative keys)
        bubble = None
        for key, stored_bubble in self._messages.items():
            if stored_bubble.message_id == message.message_id:
                bubble = stored_bubble
                break
        
        if bubble:
            bubble.update_content(message.content)
        else:
            logger.warning(f"Message {message.message_id} not found for update")

    def remove_message(self, message_id: int) -> None:
        """Remove a message from the history.

        Finds the message bubble by ID, removes it from the layout,
        and schedules it for deletion with deleteLater().

        Args:
            message_id: Message identifier to remove.
        """
        # Search for message by ID (handles both positive and negative keys)
        bubble = None
        remove_key = None
        for key, stored_bubble in self._messages.items():
            if stored_bubble.message_id == message_id:
                bubble = stored_bubble
                remove_key = key
                break
        
        if bubble and remove_key is not None:
            del self._messages[remove_key]
            bubble.deleteLater()
        else:
            logger.warning(f"Message {message_id} not found for removal")

    def _add_message_internal(self, message: Message) -> None:
        """Add a message internally (without scrolling).

        Creates a MessageBubble widget, connects its signals to
        the widget's signals, and inserts it into the layout.
        Skips if message with same ID already exists (except for
        messages with message_id=0, which are unsaved and should
        always be added).

        Args:
            message: Message entity to add.
        """
        # Generate unique key for unsaved messages (message_id=0)
        # Use negative IDs to avoid collision with saved messages
        if message.message_id == 0:
            # Unsaved message - generate unique negative key
            storage_key = next(self._unsaved_counter)
        else:
            # Saved message - use actual message_id
            storage_key = message.message_id
            # Skip duplicates for saved messages only
            if storage_key in self._messages:
                return

        # Create bubble
        bubble = MessageBubble(message)
        bubble.edit_requested.connect(self._on_bubble_edit_requested)
        bubble.delete_requested.connect(self._on_bubble_delete_requested)

        # Add to layout (before stretch)
        self._container_layout.insertWidget(
            self._container_layout.count() - 1,
            bubble,
        )

        # Store reference with unique key
        self._messages[storage_key] = bubble

    def _clear_messages(self) -> None:
        """Clear all messages from the widget.
        
        Copies the list of bubbles before deletion to avoid modifying
        the dictionary during iteration. Objects are scheduled for
        deletion with deleteLater() to ensure proper Qt cleanup.
        """
        # Copy list to avoid modifying dict during iteration
        bubbles = list(self._messages.values())
        self._messages.clear()
        
        for bubble in bubbles:
            bubble.deleteLater()

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the message list.

        Uses debouncing to prevent race conditions when multiple
        messages are added in quick succession.
        """
        if self._scroll_pending:
            return  # Scroll already scheduled

        self._scroll_pending = True
        # Use QTimer to ensure layout is updated before scrolling
        # 100ms delay to ensure Qt has time to layout all widgets
        QTimer.singleShot(100, self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self) -> None:
        """Perform the actual scroll to bottom."""
        self._scroll_pending = False
        scrollbar = self._scroll_area.verticalScrollBar()
        if scrollbar is not None:
            # Scroll to maximum value (bottom)
            scrollbar.setValue(scrollbar.maximum())
            # Force update to ensure scroll is applied
            scrollbar.update()

    def _on_bubble_edit_requested(self, message_id: int, content: str) -> None:
        """Forward edit request from bubble.

        This method is called when a user selects 'Edit' from a message's
        context menu. It re-emits the signal for the parent widget to handle.

        Args:
            message_id: Message identifier.
            content: Current message content for editing.
        """
        self.message_edit_requested.emit(message_id, content)

    def _on_bubble_delete_requested(self, message_id: int) -> None:
        """Forward delete request from bubble.

        This method is called when a user selects 'Delete' from a message's
        context menu. It re-emits the signal for the parent widget to handle.

        Args:
            message_id: Message identifier to delete.
        """
        self.message_delete_requested.emit(message_id)
