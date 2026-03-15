"""Integration tests for RepositoryFactory."""

import os
from pathlib import Path

import pytest

from src.infrastructure.config import get_settings
from src.infrastructure.repositories.factory import (
    DATABASE_TYPE_POSTGRESQL,
    DATABASE_TYPE_SQLITE,
    RepositoryFactory,
    TransactionalRepositories,
)


class TestRepositoryFactory:
    """Tests for RepositoryFactory."""

    def test_create_factory_with_valid_sqlite_config(
        self,
        temp_db_path: str,
    ) -> None:
        """Test factory creation with valid SQLite configuration."""
        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        assert factory.database_type == DATABASE_TYPE_SQLITE
        assert database_url in factory.database_url

    def test_create_factory_with_invalid_database_type(
        self,
        temp_db_path: str,
    ) -> None:
        """Test factory creation with invalid database type."""
        database_url = f"sqlite+aiosqlite:///{temp_db_path}"

        with pytest.raises(ValueError, match="Unsupported database type"):
            RepositoryFactory(
                database_type="mysql",
                database_url=database_url,
            )

    def test_create_factory_with_empty_url(self) -> None:
        """Test factory creation with empty database URL."""
        with pytest.raises(ValueError, match="Database URL cannot be empty"):
            RepositoryFactory(
                database_type=DATABASE_TYPE_SQLITE,
                database_url="",
            )

    def test_create_message_repo_sqlite(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating SQLite message repository."""
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        repo = factory.create_message_repo()

        assert isinstance(repo, SQLiteMessageRepository)
        assert repo.db_path == str(Path(temp_db_path).resolve())

    def test_create_session_repo_sqlite(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating SQLite session repository."""
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        repo = factory.create_session_repo()

        assert isinstance(repo, SQLiteSessionRepository)
        assert repo.db_path == str(Path(temp_db_path).resolve())

    def test_create_user_repo_sqlite(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating SQLite user repository."""
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        repo = factory.create_user_repo()

        assert isinstance(repo, SQLiteUserRepository)
        assert repo.db_path == str(Path(temp_db_path).resolve())

    def test_create_postgresql_repo_not_implemented(self) -> None:
        """Test that PostgreSQL repositories raise NotImplementedError."""
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_POSTGRESQL,
            database_url="postgresql+asyncpg://localhost/test",
        )

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            factory.create_message_repo()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            factory.create_session_repo()

        with pytest.raises(NotImplementedError, match="not yet implemented"):
            factory.create_user_repo()

    def test_factory_extracts_absolute_path_from_relative_url(
        self,
        tmp_path: Path,
    ) -> None:
        """Test that factory converts relative path to absolute."""
        # Change to temp directory to make relative path resolvable
        original_cwd = os.getcwd()
        try:
            os.chdir(str(tmp_path))
            db_path = tmp_path / "test.db"
            database_url = f"sqlite+aiosqlite:///{db_path.name}"

            factory = RepositoryFactory(
                database_type=DATABASE_TYPE_SQLITE,
                database_url=database_url,
            )

            repo = factory.create_message_repo()

            # Path should be absolute
            assert Path(repo.db_path).is_absolute()
            assert Path(repo.db_path).name == "test.db"
        finally:
            os.chdir(original_cwd)


class TestRepositoryFactoryWithSettings:
    """Tests for RepositoryFactory integration with Settings."""

    def test_factory_with_real_settings(
        self,
        temp_db_path: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test factory creation using real settings."""
        # Set environment variables for settings
        monkeypatch.setenv("DATABASE_TYPE", "sqlite")
        monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{temp_db_path}")
        monkeypatch.setenv("APP_NAME", "TestApp")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")

        # Force settings reload
        settings = get_settings()

        factory = RepositoryFactory(
            database_type=settings.database_type,
            database_url=settings.database_url,
        )

        assert factory.database_type == "sqlite"
        assert temp_db_path in factory.database_url

        # Should be able to create repositories
        message_repo = factory.create_message_repo()
        assert message_repo is not None


class TestRepositoryFactoryTransactional:
    """Tests for RepositoryFactory transactional mode."""

    @pytest.mark.asyncio
    async def test_create_transactional_repos(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating transactional repositories."""
        from src.infrastructure.database.unit_of_work import UnitOfWork

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        async with UnitOfWork(temp_db_path).transaction() as uow:
            repos = factory.create_transactional_repos(uow.connection)

            assert isinstance(repos, TransactionalRepositories)
            assert repos.connection is uow.connection
            assert repos.message_repo is not None
            assert repos.session_repo is not None
            assert repos.user_repo is not None

    @pytest.mark.asyncio
    async def test_transactional_repos_share_connection(
        self,
        temp_db_path: str,
    ) -> None:
        """Test that all transactional repos share the same connection."""
        from src.infrastructure.database.unit_of_work import UnitOfWork

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        async with UnitOfWork(temp_db_path).transaction() as uow:
            repos = factory.create_transactional_repos(uow.connection)

            # All repos should have the same internal connection
            assert repos.message_repo._external_connection is uow.connection
            assert repos.session_repo._external_connection is uow.connection
            assert repos.user_repo._external_connection is uow.connection

    @pytest.mark.asyncio
    async def test_create_message_repo_with_connection(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating single repository with connection."""
        from src.infrastructure.database.unit_of_work import UnitOfWork
        from src.infrastructure.repositories.sqlite_message_repo import (
            SQLiteMessageRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        async with UnitOfWork(temp_db_path).transaction() as uow:
            message_repo = factory.create_message_repo_with_connection(
                uow.connection
            )

            assert isinstance(message_repo, SQLiteMessageRepository)
            assert message_repo._external_connection is uow.connection

    @pytest.mark.asyncio
    async def test_create_session_repo_with_connection(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating session repository with connection."""
        from src.infrastructure.database.unit_of_work import UnitOfWork
        from src.infrastructure.repositories.sqlite_session_repo import (
            SQLiteSessionRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        async with UnitOfWork(temp_db_path).transaction() as uow:
            session_repo = factory.create_session_repo_with_connection(
                uow.connection
            )

            assert isinstance(session_repo, SQLiteSessionRepository)
            assert session_repo._external_connection is uow.connection

    @pytest.mark.asyncio
    async def test_create_user_repo_with_connection(
        self,
        temp_db_path: str,
    ) -> None:
        """Test creating user repository with connection."""
        from src.infrastructure.database.unit_of_work import UnitOfWork
        from src.infrastructure.repositories.sqlite_user_repo import (
            SQLiteUserRepository,
        )

        database_url = f"sqlite+aiosqlite:///{temp_db_path}"
        factory = RepositoryFactory(
            database_type=DATABASE_TYPE_SQLITE,
            database_url=database_url,
        )

        async with UnitOfWork(temp_db_path).transaction() as uow:
            user_repo = factory.create_user_repo_with_connection(uow.connection)

            assert isinstance(user_repo, SQLiteUserRepository)
            assert user_repo._external_connection is uow.connection
