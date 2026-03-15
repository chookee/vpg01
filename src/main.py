"""Application entry point.

This module provides the application entry point and dependency injection
container for assembling all application components.

Example:
    >>> app = build_app()
    >>> # Access use cases via container
    >>> result = await app.process_message.execute(session_id=1, user_text="Hello")

    >>> # Use UnitOfWork for transactional operations
    >>> async with app.create_unit_of_work().transaction() as uow:
    ...     repos = app.repository_factory.create_transactional_repos(uow.connection)
    ...     await repos.message_repo.add(message)
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.infrastructure.config import get_settings
from src.infrastructure.logging import setup_logger


@dataclass
class ApplicationContainer:
    """Dependency injection container for application components.

    Holds all initialized use cases and services for the application.
    Created by build_app() function.

    Attributes:
        process_message: Use case for processing user messages.
        view_history: Use case for viewing session history.
        edit_message: Use case for editing messages.
        delete_message: Use case for deleting messages.
        repository_factory: Factory for creating repositories.
        db_path: Absolute path to database file.
        settings: Application settings instance.
        db_semaphore: Semaphore limiting concurrent DB operations (max 10).

    Example:
        >>> app = build_app()
        >>> result = await app.process_message.execute(session_id=1, user_text="Hello")

        >>> # For transactional operations:
        >>> async with app.create_unit_of_work().transaction() as uow:
        ...     repos = app.repository_factory.create_transactional_repos(uow.connection)
        """

    process_message: Any
    view_history: Any
    edit_message: Any
    delete_message: Any
    repository_factory: Any
    db_path: str
    settings: Any
    db_semaphore: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(10)  # Max 10 concurrent DB ops
    )
    # Future use cases can be added here

    async def execute_with_db_limit(self, coro):
        """Execute coroutine with DB connection limit.

        Args:
            coro: Coroutine to execute under semaphore protection.

        Returns:
            Result of the coroutine.

        Example:
            result = await app.execute_with_db_limit(
                app.process_message.execute(session_id=1, user_text="Hello")
            )
        """
        async with self.db_semaphore:
            return await coro

    def create_unit_of_work(self) -> Any:
        """Create a new UnitOfWork instance for transactional operations.

        Returns:
            UnitOfWork instance with the configured database path.

        Example:
            async with app.create_unit_of_work().transaction() as uow:
                repos = app.repository_factory.create_transactional_repos(
                    uow.connection
                )
                await repos.message_repo.add(message)
                await repos.session_repo.create(session)
            # All operations committed atomically
        """
        from src.infrastructure.database.unit_of_work import UnitOfWork

        return UnitOfWork(self.db_path)


def build_app() -> ApplicationContainer:
    """Build and configure the application with all dependencies.

    Creates and configures:
    - Repository factory based on database type
    - Message, Session, and User repositories
    - In-memory session store for short-term memory
    - LLM service (stub implementation)
    - Context builder service
    - All use cases (ProcessMessage, ViewHistory, EditMessage, DeleteMessage)

    Returns:
        ApplicationContainer with all initialized use cases and services.
        Container provides:
        - Direct access to use cases for simple operations
        - Repository factory for creating custom repositories
        - UnitOfWork factory for transactional operations

    Raises:
        RuntimeError: If application initialization fails.
    """
    logger = logging.getLogger(__name__)
    logger.info("Building application...")

    try:
        # Load settings
        settings = get_settings()
        logger.info("Settings loaded: %s", settings.app_name)

        # Extract database path for UnitOfWork
        db_path = _extract_db_path(settings.database_url)
        logger.debug("Database path: %s", db_path)

        # Create repository factory
        from src.infrastructure.repositories.factory import RepositoryFactory

        repo_factory = RepositoryFactory(
            database_type=settings.database_type,
            database_url=settings.database_url,
        )
        logger.info(
            "Repository factory created: type=%s", settings.database_type
        )

        # Create repositories via factory (standalone mode)
        message_repo = repo_factory.create_message_repo()
        session_repo = repo_factory.create_session_repo()
        user_repo = repo_factory.create_user_repo()
        logger.debug("Repositories created")

        # Create in-memory session store for short-term memory
        from src.infrastructure.repositories.inmemory_session_store import (
            InMemorySessionStore,
        )

        short_term_store = InMemorySessionStore()
        logger.debug("In-memory session store created")

        # Create LLM service (stub implementation for now)
        from src.infrastructure.llm.ollama_service import OllamaService

        llm_service = OllamaService(
            base_url=settings.ollama_base_url,
            default_model=settings.ollama_model,
        )
        logger.info("LLM service created: provider=%s", settings.llm_provider)

        # Create context builder
        from src.application.services.context_builder import ContextBuilder

        context_builder = ContextBuilder(
            long_term_repo=message_repo,
            short_term_store=short_term_store,
        )
        logger.debug("Context builder created")

        # Create use cases
        from src.application.use_cases.process_message import ProcessMessage
        from src.application.use_cases.view_history import ViewHistory
        from src.application.use_cases.edit_message import EditMessage
        from src.application.use_cases.delete_message import DeleteMessage

        process_message = ProcessMessage(
            message_repo=message_repo,
            session_repo=session_repo,
            short_term_store=short_term_store,
            context_builder=context_builder,
            llm_service=llm_service,
            default_model=settings.ollama_model,
        )

        view_history = ViewHistory(
            message_repo=message_repo,
            session_repo=session_repo,
            short_term_store=short_term_store,
        )

        edit_message = EditMessage(
            message_repo=message_repo,
            short_term_store=short_term_store,
        )

        delete_message = DeleteMessage(
            message_repo=message_repo,
            short_term_store=short_term_store,
        )

        logger.info("Use cases created")

        # Create DB semaphore
        db_semaphore = asyncio.Semaphore(10)  # Max 10 concurrent DB operations

        return ApplicationContainer(
            process_message=process_message,
            view_history=view_history,
            edit_message=edit_message,
            delete_message=delete_message,
            repository_factory=repo_factory,
            db_path=db_path,
            settings=settings,
            db_semaphore=db_semaphore,
        )

    except Exception as e:
        logger.exception("Failed to build application: %s", e)
        raise RuntimeError(f"Failed to build application: {e}") from e


def _extract_db_path(database_url: str) -> str:
    """Extract absolute database file path from database URL.

    Args:
        database_url: Database connection URL (e.g., sqlite+aiosqlite:///./data/app.db).

    Returns:
        Absolute path to database file.

    Raises:
        ValueError: If URL scheme is not supported or path is invalid.
    """
    from src.infrastructure.repositories.factory import (
        extract_sqlite_path_from_url,
    )

    return extract_sqlite_path_from_url(database_url)


def main() -> int:
    """Main application entry point.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    logger = None
    try:
        settings = get_settings()
        logger = setup_logger(debug=settings.debug)

        logger.info("Hello, World!")
        logger.info("Application: %s", settings.app_name)
        logger.debug("Debug mode: %s", settings.debug)
        logger.info("LLM Provider: %s", settings.llm_provider)

        if settings.is_bot_configured():
            logger.info("Telegram bot: configured")
        else:
            logger.warning("Telegram bot: not configured (set TELEGRAM_BOT_TOKEN)")

        # Build application and verify DI container
        logger.info("Building application container...")
        app = build_app()
        logger.info(
            "Application container built successfully."
        )
        logger.info(
            "  Use cases: process_message, view_history, edit_message, delete_message"
        )
        logger.info(
            "  Repository factory: available for custom repository creation"
        )
        logger.info(
            "  UnitOfWork: use app.create_unit_of_work() for transactions"
        )

        return 0

    except Exception as exc:
        # Use existing logger or create fallback
        if logger is not None:
            logger.exception("Fatal error: %s", exc)
        else:
            # Fallback logger - minimal configuration
            logging.basicConfig(
                level=logging.ERROR,
                format="%(asctime)s | %(levelname)s | %(message)s",
                force=True,
            )
            logging.exception("Fatal error: %s", exc)

        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
