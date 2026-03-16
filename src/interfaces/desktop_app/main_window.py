"""Main window for the desktop application.

This module provides the main application window with:
- Message history display
- Message input field
- Send button
- Memory mode selector
- Export/Import menu items
"""

import json
import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeyEvent, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.application.use_cases.process_message import ProcessMessageResult
from src.domain.enums import MemoryMode
from src.interfaces.desktop_app.controllers import (
    DeleteMessageController,
    EditMessageController,
    ExportImportController,
    HistoryController,
    MessageController,
)
from src.interfaces.desktop_app.widgets.history_widget import HistoryWidget

logger = logging.getLogger(__name__)


class EditMessageDialog(QDialog):
    """Dialog for editing a message.

    This dialog provides a text editor for modifying message content
    with validation to prevent empty messages.

    Attributes:
        new_content: Edited message content after dialog closes.
            Updated when user clicks OK with non-empty content.

    Example:
        >>> dialog = EditMessageDialog(parent, original_content="Hello")
        >>> if dialog.exec() == QDialog.DialogCode.Accepted:
        ...     print(f"New content: {dialog.new_content}")
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        original_content: str = "",
    ) -> None:
        """Initialize EditMessageDialog.

        Args:
            parent: Parent widget for proper modal behavior.
            original_content: Original message content to edit.
                Pre-filled in the text editor.
        """
        super().__init__(parent)
        self.setWindowTitle("Редактировать сообщение")
        self.setMinimumSize(400, 300)

        self.new_content = original_content

        # Create layout
        layout = QVBoxLayout(self)

        # Label
        layout.addWidget(QLabel("Текст сообщения:"))

        # Text editor
        self._text_edit = QPlainTextEdit()
        self._text_edit.setPlainText(original_content)
        layout.addWidget(self._text_edit)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_accept(self) -> None:
        """Handle OK button click.

        Validates that content is not empty before accepting.
        Shows warning dialog if content is empty.
        """
        self.new_content = self._text_edit.toPlainText().strip()
        if not self.new_content:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Сообщение не может быть пустым",
            )
            return
        self.accept()


class MainWindow(QMainWindow):
    """Main application window for the VPg01 Desktop chat application.

    Provides the primary UI for the chat application with:
    - Message history widget with context menu (edit/delete)
    - Input field and send button
    - Memory mode selector (NO_MEMORY, SHORT_TERM, LONG_TERM, BOTH)
    - Export/Import functionality via File menu
    - Keyboard shortcut (Ctrl+Enter) for sending messages

    Attributes:
        _session_id: Current session identifier.
        _message_controller: Controller for processing messages.
        _history_controller: Controller for viewing history.
        _edit_controller: Controller for editing messages.
        _delete_controller: Controller for deleting messages.
        _export_import_controller: Controller for export/import operations.
        _export_in_progress: Flag to prevent duplicate export operations.
        _import_in_progress: Flag to prevent duplicate import operations.

    Example:
        >>> from PyQt6.QtWidgets import QApplication
        >>> app = QApplication([])
        >>> window = MainWindow(session_id=1)
        >>> window.show()
    """

    def __init__(
        self,
        session_id: Optional[int] = None,
    ) -> None:
        """Initialize MainWindow.

        Args:
            session_id: Session identifier to use for this window.
                If None, will be auto-created on first launch via
                DesktopSessionManager. Defaults to auto-creation.
        """
        super().__init__()

        self._session_id: Optional[int] = session_id
        self._message_controller: Optional[MessageController] = None
        self._history_controller: Optional[HistoryController] = None
        self._edit_controller: Optional[EditMessageController] = None
        self._delete_controller: Optional[DeleteMessageController] = None
        self._export_import_controller: Optional[ExportImportController] = None

        # Flags to prevent duplicate operations
        self._export_in_progress = False
        self._import_in_progress = False

        self._setup_ui()
        self._setup_controllers()
        # Session will be initialized in _initialize_session()

    def _setup_ui(self) -> None:
        """Set up the user interface components.

        Creates and configures:
        - Menu bar with File menu (Export, Import, Exit)
        - Splitter with history widget (top) and input area (bottom)
        - Memory mode selector dropdown
        - Message input field with placeholder
        - Send button
        - Status bar for operation feedback
        - Keyboard shortcut Ctrl+Return for sending

        Layout proportions: 70% history, 30% input.
        """
        self.setWindowTitle("VPg01 Desktop")
        self.setMinimumSize(800, 600)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Create menu bar
        self._create_menu_bar()

        # Create splitter for resizable panes
        splitter = QSplitter(Qt.Orientation.Vertical)

        # History widget (top pane)
        self._history_widget = HistoryWidget()
        self._history_widget.message_edit_requested.connect(
            self._on_edit_message_requested
        )
        self._history_widget.message_delete_requested.connect(
            self._on_delete_message_requested
        )
        splitter.addWidget(self._history_widget)

        # Input area (bottom pane)
        input_widget = QWidget()
        input_layout = QGridLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        # Memory mode selector
        input_layout.addWidget(QLabel("Режим памяти:"), 0, 0)

        self._mode_selector = QComboBox()
        self._mode_selector.addItem("Без памяти", MemoryMode.NO_MEMORY)
        self._mode_selector.addItem("Краткосрочная", MemoryMode.SHORT_TERM)
        self._mode_selector.addItem("Долгосрочная", MemoryMode.LONG_TERM)
        self._mode_selector.addItem("Обе", MemoryMode.BOTH)
        self._mode_selector.setCurrentIndex(1)  # Default: SHORT_TERM
        input_layout.addWidget(self._mode_selector, 0, 1)

        # Input field
        self._input_field = QPlainTextEdit()
        self._input_field.setPlaceholderText("Введите сообщение...")
        self._input_field.setMaximumBlockCount(100)
        self._input_field.setFixedHeight(80)
        input_layout.addWidget(self._input_field, 1, 0, 1, 2)

        # Send button
        self._send_button = QPushButton("Отправить")
        self._send_button.clicked.connect(self._on_send_clicked)
        input_layout.addWidget(self._send_button, 2, 1, Qt.AlignmentFlag.AlignRight)

        # Add input area to splitter
        splitter.addWidget(input_widget)

        # Set splitter sizes (70% history, 30% input)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        main_layout.addWidget(splitter)

        # Add keyboard shortcut for sending (Ctrl+Enter)
        QShortcut(
            QKeySequence("Ctrl+Return"),
            self,
            activated=self._on_send_clicked,
        )

        # Status bar
        self._status_bar = QLabel()
        self.statusBar().addPermanentWidget(self._status_bar)
        self._status_bar.setText("Готов")

    def _create_menu_bar(self) -> None:
        """Create the menu bar with File menu.

        File menu contains:
        - Export History (Ctrl+S): Export session history to JSON file
        - Import History (Ctrl+O): Import session history from JSON file
        - Exit (Ctrl+Q): Close the application
        """
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("Файл")

        # Export action
        export_action = QAction("Экспорт истории...", self)
        export_action.setShortcut(QKeySequence.StandardKey.Save)
        export_action.triggered.connect(self._on_export_triggered)
        file_menu.addAction(export_action)

        # Import action
        import_action = QAction("Импорт истории...", self)
        import_action.setShortcut(QKeySequence.StandardKey.Open)
        import_action.triggered.connect(self._on_import_triggered)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        # Exit action
        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _setup_controllers(self) -> None:
        """Set up controllers from application container.

        Initializes all controllers by building the application container
        and creating controller instances for:
        - MessageController: Processing user messages
        - HistoryController: Viewing session history
        - EditMessageController: Editing messages
        - DeleteMessageController: Deleting messages
        - ExportImportController: Export/import operations

        After controllers are set up, initializes the session automatically.

        Raises:
            RuntimeError: If application container cannot be built.
            Shows critical error dialog on failure.
        """
        # Import application container
        from src.main import build_app

        try:
            app = build_app()

            self._message_controller = MessageController(
                process_message=app.process_message
            )
            self._history_controller = HistoryController(
                view_history=app.view_history
            )
            self._edit_controller = EditMessageController(
                edit_message=app.edit_message
            )
            self._delete_controller = DeleteMessageController(
                delete_message=app.delete_message
            )
            self._export_import_controller = ExportImportController(
                export_history=app.export_history,
                import_history=app.import_history,
            )

            logger.info("Desktop app controllers initialized")

            # Initialize session after controllers are ready
            self._initialize_session()

        except Exception as e:
            logger.exception(f"Failed to initialize controllers: {e}")
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось инициализировать контроллеры: {e}",
            )
            raise

    def _initialize_session(self) -> None:
        """Initialize session for desktop application.

        Automatically creates or retrieves a session for the desktop
        user. This eliminates the need for manual session setup or
        Telegram bot interaction.

        On success:
            - Sets self._session_id to the session ID
            - Loads history for the session
            - Updates status bar with session info

        On error:
            - Shows error dialog
            - Disables message input
        """
        async def _init() -> None:
            try:
                from src.main import build_app

                app = build_app()
                db_path = app.db_path

                # Import session manager
                from src.interfaces.desktop_app.session_manager import (
                    DesktopSessionManager,
                )

                self._status_bar.setText("Инициализация сессии...")

                # Get or create session
                session_manager = DesktopSessionManager(db_path)
                self._session_id = await session_manager.get_or_create_session()

                logger.info(f"Desktop session initialized: {self._session_id}")
                self._status_bar.setText(
                    f"Сессия: {self._session_id} (готов к работе)"
                )

                # Load history after session is ready
                self._load_history()

            except Exception as e:
                logger.exception(f"Failed to initialize session: {e}")
                self._status_bar.setText("Ошибка инициализации сессии")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось инициализировать сессию: {e}\n\n"
                    f"Убедитесь, что база данных существует и инициализирована.",
                )
                # Disable input controls
                self._input_field.setEnabled(False)
                self._send_button.setEnabled(False)

        # Schedule async initialization
        QTimer.singleShot(100, lambda: self._run_async(_init()))

    def _load_history(self) -> None:
        """Load session history from storage.

        Asynchronously loads messages for the current session and
        populates the history widget. Updates status bar with
        message count on success or error message on failure.

        Uses QTimer to schedule async load after UI is ready.
        """
        if not self._history_controller:
            return

        async def _load() -> None:
            try:
                messages = await self._history_controller.get_history(
                    self._session_id
                )
                self._history_widget.set_messages(messages)
                self._status_bar.setText(f"Загружено сообщений: {len(messages)}")
            except Exception as e:
                logger.exception(f"Failed to load history: {e}")
                self._status_bar.setText("Ошибка загрузки истории")

        # Schedule async load
        QTimer.singleShot(100, lambda: self._run_async(_load()))

    def _run_async(self, coro):
        """Run async coroutine in Qt event loop.

        This method bridges async coroutines with Qt's synchronous
        signal/slot system. It schedules the coroutine in the qasync
        event loop and adds error handling to prevent silent failures.

        Args:
            coro: Coroutine to run in the event loop.

        Note:
            Exceptions in the coroutine are logged but not shown to user.
            Use try/except within the coroutine for user-facing errors.
        """
        import asyncio

        # Get the running event loop (qasync loop in Qt context)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop - should not happen in Qt context, but handle gracefully
            logger.warning("No running event loop found, creating new one")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        task = loop.create_task(coro)

        # Add callback to handle exceptions and prevent silent failures
        def _handle_task_result(t):
            try:
                t.result()
            except asyncio.CancelledError:
                logger.debug("Task was cancelled")
            except Exception as e:
                logger.exception(f"Async task failed: {e}")

        task.add_done_callback(_handle_task_result)

    def _on_send_clicked(self) -> None:
        """Handle send button click.

        Extracts text from input field, clears it, and sends
        to ProcessMessage use case with selected memory mode.
        Appends both user and assistant messages to history widget.

        Disables send button during processing to prevent duplicate sends.
        Shows error dialog if message processing fails.

        Note:
            If session is not yet initialized, shows error and prevents send.
        """
        user_text = self._input_field.toPlainText().strip()
        if not user_text:
            return

        # Check if session is initialized
        if self._session_id is None:
            QMessageBox.warning(
                self,
                "Сессия не инициализирована",
                "Подождите завершения инициализации сессии...",
            )
            return

        # Clear input field
        self._input_field.clear()

        # Get selected mode
        mode: MemoryMode | None = self._mode_selector.currentData()
        if mode is None:
            # Fallback to SHORT_TERM if mode is not set (should not happen)
            mode = MemoryMode.SHORT_TERM

        async def _send() -> None:
            try:
                self._status_bar.setText("Отправка...")
                self._send_button.setEnabled(False)

                if not self._message_controller:
                    raise RuntimeError("Message controller not initialized")

                result = await self._message_controller.process_user_message(
                    session_id=self._session_id,
                    user_text=user_text,
                    mode=mode,
                )

                # Add messages to history widget
                logger.debug(
                    f"Adding user message to history: {result.user_message.message_id}"
                )
                self._history_widget.add_message(result.user_message)
                
                logger.debug(
                    f"Adding assistant message to history: {result.assistant_message.message_id}, "
                    f"content: {result.assistant_message.content[:100]}..."
                )
                self._history_widget.add_message(result.assistant_message)

                self._status_bar.setText("Сообщение отправлено")

            except Exception as e:
                logger.exception(f"Failed to send message: {e}")
                self._status_bar.setText("Ошибка отправки сообщения")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось отправить сообщение: {e}",
                )
            finally:
                self._send_button.setEnabled(True)

        self._run_async(_send())

    def _on_edit_message_requested(self, message_id: int, current_content: str) -> None:
        """Handle edit message request from history widget.

        Opens edit dialog, and if user confirms changes, calls
        EditMessage use case to update the message in storage.
        Updates the history widget with the new content.

        Args:
            message_id: Message identifier to edit.
            current_content: Current message content for pre-fill.
        """
        dialog = EditMessageDialog(self, current_content)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_content = dialog.new_content
        if not new_content:
            return

        async def _edit() -> None:
            try:
                if not self._edit_controller:
                    raise RuntimeError("Edit controller not initialized")

                updated_message = await self._edit_controller.edit_message(
                    message_id=message_id,
                    new_content=new_content,
                )

                # Update message in history widget
                self._history_widget.update_message(updated_message)
                self._status_bar.setText("Сообщение обновлено")

            except Exception as e:
                logger.exception(f"Failed to edit message: {e}")
                self._status_bar.setText("Ошибка редактирования")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось редактировать сообщение: {e}",
                )

        self._run_async(_edit())

    def _on_delete_message_requested(self, message_id: int) -> None:
        """Handle delete message request from history widget.

        Shows confirmation dialog before deleting. If confirmed,
        calls DeleteMessage use case and removes message from
        the history widget.

        Args:
            message_id: Message identifier to delete.
        """
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите удалить это сообщение?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        async def _delete() -> None:
            try:
                if not self._delete_controller:
                    raise RuntimeError("Delete controller not initialized")

                await self._delete_controller.delete_message(message_id=message_id)

                # Remove message from history widget
                self._history_widget.remove_message(message_id)
                self._status_bar.setText("Сообщение удалено")

            except Exception as e:
                logger.exception(f"Failed to delete message: {e}")
                self._status_bar.setText("Ошибка удаления")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось удалить сообщение: {e}",
                )

        self._run_async(_delete())

    def _on_export_triggered(self) -> None:
        """Handle export history menu action.

        Opens file save dialog, and if path is selected, exports
        session history to JSON file. Shows success/error message
        after operation completes.

        Uses _export_in_progress flag to prevent duplicate exports.

        Note:
            If session is not yet initialized, shows error and prevents export.
        """
        # Check if session is initialized
        if self._session_id is None:
            QMessageBox.warning(
                self,
                "Сессия не инициализирована",
                "Невозможно экспортировать историю: сессия не инициализирована.",
            )
            return

        # Prevent duplicate export operations
        if self._export_in_progress:
            logger.warning("Export already in progress, ignoring request")
            return

        # Ask for file path
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт истории",
            "",
            "JSON файлы (*.json);;Все файлы (*)",
        )
        if not file_path:
            return

        async def _export() -> None:
            self._export_in_progress = True
            try:
                if not self._export_import_controller:
                    raise RuntimeError("Export/Import controller not initialized")

                json_data = await self._export_import_controller.export_history(
                    session_id=self._session_id
                )

                # Write to file
                Path(file_path).write_text(json_data, encoding="utf-8")

                self._status_bar.setText(f"История экспортирована: {file_path}")
                QMessageBox.information(
                    self,
                    "Успех",
                    f"История успешно экспортирована в:\n{file_path}",
                )

            except Exception as e:
                logger.exception(f"Failed to export history: {e}")
                self._status_bar.setText("Ошибка экспорта")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось экспортировать историю: {e}",
                )
            finally:
                self._export_in_progress = False

        self._run_async(_export())

    def _on_import_triggered(self) -> None:
        """Handle import history menu action.

        Opens file open dialog, and if file is selected, imports
        session history from JSON file. Shows confirmation before
        importing and reloads history after successful import.

        Uses _import_in_progress flag to prevent duplicate imports.
        Imported messages are added to existing messages (not replaced).

        Note:
            If session is not yet initialized, shows error and prevents import.
        """
        # Check if session is initialized
        if self._session_id is None:
            QMessageBox.warning(
                self,
                "Сессия не инициализирована",
                "Невозможно импортировать историю: сессия не инициализирована.",
            )
            return

        # Prevent duplicate import operations
        if self._import_in_progress:
            logger.warning("Import already in progress, ignoring request")
            return

        # Ask for file path
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт истории",
            "",
            "JSON файлы (*.json);;Все файлы (*)",
        )
        if not file_path:
            return

        # Confirm import (it will add messages, not replace)
        confirm = QMessageBox.question(
            self,
            "Подтверждение импорта",
            "Импортированные сообщения будут добавлены к существующим.\n"
            "Продолжить?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        async def _import() -> None:
            self._import_in_progress = True
            try:
                if not self._export_import_controller:
                    raise RuntimeError("Export/Import controller not initialized")

                json_data = Path(file_path).read_text(encoding="utf-8")

                result_str = (
                    await self._export_import_controller.import_history(
                        session_id=self._session_id,
                        json_data=json_data,
                    )
                )

                # Reload history to show imported messages
                self._load_history()

                self._status_bar.setText(f"Импорт: {result_str}")
                QMessageBox.information(
                    self,
                    "Импорт завершён",
                    f"Результат импорта:\n{result_str}",
                )

            except Exception as e:
                logger.exception(f"Failed to import history: {e}")
                self._status_bar.setText("Ошибка импорта")
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось импортировать историю: {e}",
                )
            finally:
                self._import_in_progress = False

        self._run_async(_import())
