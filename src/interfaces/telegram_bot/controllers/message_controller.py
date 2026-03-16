"""Message controller for Telegram bot.

This controller bridges Telegram message handlers with the application's
ProcessMessage use case, handling user and session management.

Example:
    >>> controller = MessageController(process_message, unit_of_work, repo_factory)
    >>> result = await controller.process_user_message(session_id=1, user_text="Hello")
"""

import logging
from dataclasses import dataclass

from src.application.use_cases.process_message import ProcessMessage
from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.infrastructure.database.unit_of_work import UnitOfWork
from src.infrastructure.repositories.factory import RepositoryFactory

logger = logging.getLogger(__name__)


@dataclass
class ProcessMessageResult:
    """Result of processing a user message.

    Attributes:
        response: Generated response text.
    """

    response: str


class MessageController:
    """Controller for processing user messages.

    Coordinates between Telegram handlers and ProcessMessage use case,
    managing user sessions and memory modes.
    """

    def __init__(
        self,
        process_message: ProcessMessage,
        unit_of_work: UnitOfWork,
        repo_factory: RepositoryFactory,
    ) -> None:
        """Initialize MessageController.

        Args:
            process_message: ProcessMessage use case instance.
            unit_of_work: Unit of work for transactional operations.
            repo_factory: Repository factory for creating repositories.
        """
        self._process_message = process_message
        self._unit_of_work = unit_of_work
        self._repo_factory = repo_factory

    async def process_user_message(
        self,
        session_id: int,
        user_text: str,
    ) -> ProcessMessageResult:
        """Process a user message and return the response.

        Args:
            session_id: Session identifier.
            user_text: User message text.

        Returns:
            ProcessMessageResult with response text.

        Raises:
            Exception: Propagates any errors from use case.
        """
        logger.debug(f"Processing message for session {session_id}")

        result = await self._process_message.execute(
            session_id=session_id,
            user_text=user_text,
        )

        return ProcessMessageResult(response=result.response)

    async def get_session_mode(self, session_id: int) -> MemoryMode:
        """Get current memory mode for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Current memory mode.
        """
        async with self._unit_of_work.transaction() as uow:
            repos = self._repo_factory.create_transactional_repos(uow.connection)
            session = await repos.session_repo.get(session_id)

            if session is None:
                raise ValueError(f"Session {session_id} not found")

            return session.memory_mode
