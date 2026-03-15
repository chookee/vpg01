"""Integration tests for build_app and ApplicationContainer."""

import os

import pytest

from src.main import ApplicationContainer, build_app


class TestBuildApp:
    """Tests for build_app function and ApplicationContainer."""

    @pytest.fixture
    def app_config(
        self,
        temp_db_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Configure environment for application building."""
        monkeypatch.setenv("DATABASE_TYPE", "sqlite")
        monkeypatch.setenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{temp_db_path}"
        )
        monkeypatch.setenv("APP_NAME", "TestApp")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3")

    def test_build_app_returns_container(
        self,
        app_config: None,
    ) -> None:
        """Test that build_app returns ApplicationContainer."""
        app = build_app()

        assert isinstance(app, ApplicationContainer)

    def test_container_has_all_use_cases(
        self,
        app_config: None,
    ) -> None:
        """Test that container contains all required use cases."""
        app = build_app()

        assert app.process_message is not None
        assert app.view_history is not None
        assert app.edit_message is not None
        assert app.delete_message is not None
        assert app.settings is not None

    def test_container_settings_are_valid(
        self,
        app_config: None,
    ) -> None:
        """Test that settings in container are valid."""
        app = build_app()

        assert app.settings.app_name == "TestApp"
        assert app.settings.database_type == "sqlite"
        assert app.settings.debug is True
        assert app.settings.llm_provider == "ollama"

    def test_use_cases_have_correct_type(
        self,
        app_config: None,
    ) -> None:
        """Test that use cases have correct types."""
        from src.application.use_cases.delete_message import DeleteMessage
        from src.application.use_cases.edit_message import EditMessage
        from src.application.use_cases.process_message import ProcessMessage
        from src.application.use_cases.view_history import ViewHistory

        app = build_app()

        assert isinstance(app.process_message, ProcessMessage)
        assert isinstance(app.view_history, ViewHistory)
        assert isinstance(app.edit_message, EditMessage)
        assert isinstance(app.delete_message, DeleteMessage)

    def test_build_app_with_invalid_database_type(
        self,
        temp_db_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that build_app raises error with invalid database type."""
        monkeypatch.setenv("DATABASE_TYPE", "mysql")
        monkeypatch.setenv(
            "DATABASE_URL", f"sqlite+aiosqlite:///{temp_db_path}"
        )
        monkeypatch.setenv("APP_NAME", "TestApp")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        with pytest.raises(RuntimeError, match="Failed to build application"):
            build_app()

    def test_build_app_creates_repositories(
        self,
        app_config: None,
        temp_db_path: str,
    ) -> None:
        """Test that build_app creates repositories successfully."""
        app = build_app()
        assert app is not None

        # Verify repositories are created by checking their type
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        # Access use cases to verify they have repositories
        assert hasattr(app.process_message, "_message_repo")
        assert hasattr(app.process_message, "_session_repo")
        assert hasattr(app.view_history, "_message_repo")
        assert hasattr(app.view_history, "_session_repo")

        # Verify repository types
        assert isinstance(
            app.process_message._message_repo, SQLiteMessageRepository
        )
        assert isinstance(
            app.process_message._session_repo, SQLiteSessionRepository
        )

    def test_container_has_repository_factory(
        self,
        app_config: None,
    ) -> None:
        """Test that container has repository factory."""
        from src.infrastructure.repositories.factory import RepositoryFactory

        app = build_app()

        assert app.repository_factory is not None
        assert isinstance(app.repository_factory, RepositoryFactory)

    def test_container_has_db_path(
        self,
        app_config: None,
        temp_db_path: str,
    ) -> None:
        """Test that container has database path."""
        app = build_app()

        assert app.db_path is not None
        assert temp_db_path in app.db_path or app.db_path.endswith(temp_db_path)

    def test_container_create_unit_of_work(
        self,
        app_config: None,
    ) -> None:
        """Test that container can create UnitOfWork."""
        from src.infrastructure.database.unit_of_work import UnitOfWork

        app = build_app()

        uow = app.create_unit_of_work()
        assert isinstance(uow, UnitOfWork)
        assert uow.db_path == app.db_path

    @pytest.mark.asyncio
    async def test_container_transactional_integration(
        self,
        app_config: None,
        temp_db_path: str,
    ) -> None:
        """Test full integration: container -> UnitOfWork -> transactional repos."""
        import aiosqlite
        from src.infrastructure.repositories.factory import (
            TransactionalRepositories,
        )

        # Pre-create tables
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
                "INSERT INTO users (user_id, telegram_id, default_mode) VALUES (1, 123, 'short_term');"
            )
            await db.execute(
                "INSERT INTO sessions (session_id, user_id, memory_mode) VALUES (1, 1, 'short_term');"
            )
            await db.commit()

        app = build_app()

        # Use UnitOfWork via container
        async with app.create_unit_of_work().transaction() as uow:
            repos = app.repository_factory.create_transactional_repos(
                uow.connection
            )

            assert isinstance(repos, TransactionalRepositories)
            assert repos.connection is uow.connection

            # Verify repos work
            messages = await repos.message_repo.get_by_session(1)
            assert isinstance(messages, list)
