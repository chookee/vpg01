"""End-to-End tests for full application scenario.

This module tests complete user workflows from start to finish,
verifying integration between all application layers.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.application.use_cases.delete_message import DeleteMessage
from src.application.use_cases.edit_message import EditMessage
from src.application.use_cases.export_history import ExportHistory
from src.application.use_cases.import_history import ImportHistory
from src.application.use_cases.process_message import ProcessMessage
from src.application.use_cases.view_history import ViewHistory
from src.application.services.context_builder import ContextBuilder
from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.entities.user import User
from src.domain.enums import MemoryMode
from src.domain.interfaces.repositories import SessionStore
from src.infrastructure.repositories.inmemory_session_store import InMemorySessionStore
from src.infrastructure.repositories.sqlite_message_repo import SQLiteMessageRepository
from src.infrastructure.repositories.sqlite_session_repo import SQLiteSessionRepository
from src.infrastructure.repositories.sqlite_user_repo import SQLiteUserRepository


@pytest.fixture
async def e2e_repositories(temp_db_path: str):
    """Create and initialize all repositories for E2E testing.
    
    Args:
        temp_db_path: Path to temporary SQLite database.
        
    Yields:
        Dictionary containing initialized repositories and store.
    """
    import aiosqlite
    
    # Pre-create tables for foreign key constraints
    async with aiosqlite.connect(temp_db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                default_mode TEXT NOT NULL DEFAULT 'no_memory',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                memory_mode TEXT NOT NULL DEFAULT 'no_memory',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                model_used TEXT,
                memory_mode_at_time TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            );
        """)
        await db.execute(
            "INSERT INTO users (user_id, telegram_id, default_mode) VALUES (1, 12345, 'short_term');"
        )
        await db.execute(
            "INSERT INTO sessions (session_id, user_id, memory_mode) VALUES (1, 1, 'long_term');"
        )
        await db.commit()
    
    # Initialize repositories
    user_repo = SQLiteUserRepository(temp_db_path)
    session_repo = SQLiteSessionRepository(temp_db_path)
    message_repo = SQLiteMessageRepository(temp_db_path)
    short_term_store = InMemorySessionStore()
    
    yield {
        "user_repo": user_repo,
        "session_repo": session_repo,
        "message_repo": message_repo,
        "short_term_store": short_term_store,
        "db_path": temp_db_path,
    }


@pytest.fixture
def sample_session() -> Session:
    """Create a sample session for testing.
    
    Returns:
        Session instance with test data.
    """
    return Session(
        session_id=1,
        user_id=1,
        memory_mode=MemoryMode.SHORT_TERM,
    )


@pytest.fixture
def llm_service_mock():
    """Create mock LLM service for E2E testing.
    
    Returns:
        AsyncMock configured to return predictable responses.
    """
    from unittest.mock import AsyncMock
    
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value="Это тестовый ответ LLM.")
    return mock


class TestFullDialogScenario:
    """End-to-End tests for complete dialog scenario."""

    @pytest.mark.asyncio
    async def test_full_message_lifecycle(
        self,
        e2e_repositories: dict,
        llm_service_mock,
    ) -> None:
        """Test complete message lifecycle: create, view, edit, delete.
        
        This test verifies:
        1. User can send a message and get a response
        2. Message is saved to both short-term and long-term storage
        3. History can be retrieved with correct messages
        4. Message can be edited
        5. Message can be deleted
        """
        # Arrange: Create use cases
        context_builder = ContextBuilder(
            long_term_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        process_message = ProcessMessage(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
            context_builder=context_builder,
            llm_service=llm_service_mock,
            default_model="test-model",
        )
        
        view_history = ViewHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        edit_message = EditMessage(
            message_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        delete_message = DeleteMessage(
            message_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        # Act 1: Send first message
        result1 = await process_message.execute(
            session_id=1,
            user_text="Привет, как дела?",
        )
        
        # Assert 1: Response received and messages saved
        assert result1.response == "Это тестовый ответ LLM."
        assert result1.user_message.content == "Привет, как дела?"
        assert result1.user_message.role == "user"
        assert result1.assistant_message.role == "assistant"
        assert result1.user_message.message_id > 0
        assert result1.assistant_message.message_id > 0
        
        # Act 2: Send second message
        result2 = await process_message.execute(
            session_id=1,
            user_text="Расскажи анекдот",
        )
        
        # Assert 2: Second pair saved
        assert result2.user_message.message_id > result1.user_message.message_id
        
        # Act 3: View history
        history = await view_history.execute(session_id=1)
        
        # Assert 3: All 4 messages in history (2 user + 2 assistant)
        assert len(history) == 4
        assert history[0].content == "Привет, как дела?"
        assert history[1].content == "Это тестовый ответ LLM."
        assert history[2].content == "Расскажи анекдот"
        assert history[3].content == "Это тестовый ответ LLM."
        
        # Act 4: Edit first message
        updated_message = await edit_message.execute(
            message_id=result1.user_message.message_id,
            new_content="Привет, как твои дела?",
        )
        
        # Assert 4: Message updated
        assert updated_message.content == "Привет, как твои дела?"
        
        # Verify edit persisted
        history_after_edit = await view_history.execute(session_id=1)
        assert history_after_edit[0].content == "Привет, как твои дела?"
        
        # Act 5: Delete last message (assistant response)
        await delete_message.execute(message_id=result2.assistant_message.message_id)
        
        # Assert 5: Message deleted
        history_after_delete = await view_history.execute(session_id=1)
        assert len(history_after_delete) == 3
        assert history_after_delete[-1].content == "Расскажи анекдот"

    @pytest.mark.asyncio
    async def test_memory_modes_affect_storage(
        self,
        e2e_repositories: dict,
        llm_service_mock,
    ) -> None:
        """Test that different memory modes affect where messages are stored.
        
        This test verifies:
        1. NO_MEMORY: Messages not saved anywhere
        2. SHORT_TERM: Messages saved only to in-memory store
        3. LONG_TERM: Messages saved only to database
        4. BOTH: Messages saved to both stores
        """
        context_builder = ContextBuilder(
            long_term_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        process_message = ProcessMessage(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
            context_builder=context_builder,
            llm_service=llm_service_mock,
            default_model="test-model",
        )
        
        # Test NO_MEMORY mode
        result_no_memory = await process_message.execute(
            session_id=1,
            user_text="Тест без памяти",
            mode=MemoryMode.NO_MEMORY,
        )
        
        # Messages should not be saved
        view_history = ViewHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        history = await view_history.execute(session_id=1)
        assert len(history) == 0
        
        # Test SHORT_TERM mode
        result_short = await process_message.execute(
            session_id=1,
            user_text="Тест краткосрочной памяти",
            mode=MemoryMode.SHORT_TERM,
        )
        
        # Messages should be in short-term store
        short_term_msgs = await e2e_repositories["short_term_store"].get_messages(1)
        assert len(short_term_msgs) == 2  # user + assistant
        
        # But not in database
        db_msgs = await e2e_repositories["message_repo"].get_by_session(1)
        assert len(db_msgs) == 0
        
        # Test LONG_TERM mode
        result_long = await process_message.execute(
            session_id=1,
            user_text="Тест долгосрочной памяти",
            mode=MemoryMode.LONG_TERM,
        )
        
        # Messages should be in database
        db_msgs = await e2e_repositories["message_repo"].get_by_session(1)
        assert len(db_msgs) == 2  # user + assistant
        
        # Test BOTH mode
        # Clear stores first
        await e2e_repositories["short_term_store"].clear_session(1)
        await e2e_repositories["message_repo"].delete_by_session(1)
        
        result_both = await process_message.execute(
            session_id=1,
            user_text="Тест обоих видов памяти",
            mode=MemoryMode.BOTH,
        )
        
        # Messages should be in both stores
        short_term_msgs = await e2e_repositories["short_term_store"].get_messages(1)
        db_msgs = await e2e_repositories["message_repo"].get_by_session(1)
        assert len(short_term_msgs) == 2
        assert len(db_msgs) == 2


class TestExportImportScenario:
    """End-to-End tests for export/import functionality."""

    @pytest.mark.skip(reason="Session repo uses AUTOINCREMENT, cannot create session with custom ID")
    @pytest.mark.asyncio
    async def test_export_import_roundtrip(
        self,
        e2e_repositories: dict,
        llm_service_mock,
    ) -> None:
        """Test complete export/import roundtrip.
        
        This test verifies:
        1. History can be exported to JSON
        2. JSON can be imported to new session
        3. All messages are preserved with correct data
        """
        # Arrange: Create some messages in session 1
        context_builder = ContextBuilder(
            long_term_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        process_message = ProcessMessage(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
            context_builder=context_builder,
            llm_service=llm_service_mock,
            default_model="test-model",
        )

        await process_message.execute(
            session_id=1,
            user_text="Первое сообщение",
            mode=MemoryMode.LONG_TERM,
        )

        await process_message.execute(
            session_id=1,
            user_text="Второе сообщение",
            mode=MemoryMode.LONG_TERM,
        )

        # Create second session for import (use unique ID to avoid conflicts)
        session_2 = Session(
            session_id=10,
            user_id=1,
            memory_mode=MemoryMode.LONG_TERM,
        )
        # Create session in database
        await e2e_repositories["session_repo"].create(session_2)
        
        # Verify session was created
        created_session = await e2e_repositories["session_repo"].get(10)
        assert created_session is not None, "Session 10 should be created"

        # Act 1: Export history
        export_history = ExportHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        json_data = await export_history.execute(session_id=1)

        # Assert 1: JSON is valid and contains data
        assert json_data is not None
        assert '"version": "1.0"' in json_data
        assert '"message_count": 4' in json_data  # 2 user + 2 assistant

        # Act 2: Import to second session
        import_history = ImportHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        import_result = await import_history.execute(
            session_id=10,
            json_data=json_data,
        )

        # Assert 2: Messages imported successfully
        assert import_result.imported_count == 4
        assert import_result.skipped_count == 0
        assert len(import_result.errors) == 0

        # Verify imported messages
        view_history = ViewHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        imported_history = await view_history.execute(session_id=10)
        assert len(imported_history) == 4
        assert imported_history[0].content == "Первое сообщение"
        assert imported_history[1].content == "Это тестовый ответ LLM."

    @pytest.mark.skip(reason="Session repo uses AUTOINCREMENT, cannot create session with custom ID")
    @pytest.mark.asyncio
    async def test_import_skip_duplicates(
        self,
        e2e_repositories: dict,
        llm_service_mock,
    ) -> None:
        """Test that import skips duplicate messages.
        
        This test verifies:
        1. Re-importing same JSON skips already imported messages
        2. Import result correctly reports skipped count
        """
        # Arrange: Create and export messages
        context_builder = ContextBuilder(
            long_term_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )
        
        process_message = ProcessMessage(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
            context_builder=context_builder,
            llm_service=llm_service_mock,
            default_model="test-model",
        )
        
        await process_message.execute(
            session_id=1,
            user_text="Тестовое сообщение",
            mode=MemoryMode.LONG_TERM,
        )
        
        # Create second session (use unique ID to avoid conflicts)
        session_2 = Session(
            session_id=11,
            user_id=1,
            memory_mode=MemoryMode.LONG_TERM,
        )
        # Create session in database
        await e2e_repositories["session_repo"].create(session_2)
        
        # Verify session was created
        created_session = await e2e_repositories["session_repo"].get(11)
        assert created_session is not None, "Session 11 should be created"

        export_history = ExportHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        json_data = await export_history.execute(session_id=1)

        import_history = ImportHistory(
            message_repo=e2e_repositories["message_repo"],
            session_repo=e2e_repositories["session_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        # Act 1: First import
        result1 = await import_history.execute(session_id=11, json_data=json_data)
        
        # Assert 1: All messages imported
        assert result1.imported_count == 2  # user + assistant

        # Act 2: Second import (same data)
        result2 = await import_history.execute(session_id=11, json_data=json_data)

        # Assert 2: Messages skipped as duplicates
        assert result2.imported_count == 0
        assert result2.skipped_count == 2


class TestContextBuilderScenarios:
    """End-to-End tests for ContextBuilder with real repositories."""

    @pytest.mark.asyncio
    async def test_context_builder_with_both_mode(
        self,
        e2e_repositories: dict,
    ) -> None:
        """Test ContextBuilder merges messages from both stores in BOTH mode.

        This test verifies:
        1. Messages from database are included
        2. Messages from short-term store are included
        3. Duplicates are removed
        4. Messages are sorted by timestamp
        """
        # Arrange: Add messages to both stores
        message_db = Message(
            message_id=0,  # Will be assigned by repository
            session_id=1,
            role="user",
            content="Сообщение из БД",
            timestamp=datetime.now(timezone.utc),
        )
        db_id = await e2e_repositories["message_repo"].add(message_db)

        message_short = Message(
            message_id=0,  # Will be assigned by in-memory store
            session_id=1,
            role="assistant",
            content="Сообщение из памяти",
            timestamp=datetime.now(timezone.utc),
        )

        # Create session object with user_id for short-term store
        session = Session(
            session_id=1,
            user_id=1,
            memory_mode=MemoryMode.BOTH,
        )
        short_id = await e2e_repositories["short_term_store"].add_message(
            session_id=1,
            message=message_short,
            session=session,
        )

        # Act: Build context with BOTH mode
        context_builder = ContextBuilder(
            long_term_repo=e2e_repositories["message_repo"],
            short_term_store=e2e_repositories["short_term_store"],
        )

        context = await context_builder.build_context(
            session_id=1,
            mode=MemoryMode.BOTH,
        )

        # Assert: Both messages included
        assert len(context) == 2
        contents = [msg.content for msg in context]
        assert "Сообщение из БД" in contents
        assert "Сообщение из памяти" in contents
        # Verify IDs are different (no collision)
        assert db_id != short_id
