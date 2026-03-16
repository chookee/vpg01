"""ProcessMessage use case for handling user messages.

This use case orchestrates the flow of processing a user message:
1. Validates input data.
2. Builds conversation context via ContextBuilder.
3. Calls LLM service to generate a response.
4. Saves user and assistant messages to long-term storage.
5. Optionally saves to short-term storage based on memory mode.

Memory Mode Behavior:
    - NO_MEMORY: Messages are NOT saved (stateless conversation).
    - SHORT_TERM: Messages saved to in-memory store only.
    - LONG_TERM: Messages saved to database only.
    - BOTH: Messages saved to both stores.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.domain.entities.session import Session
from src.application.services.context_builder import ContextBuilder
from src.domain.entities.message import Message
from src.domain.enums import MemoryMode
from src.domain.exceptions import (
    InvalidDataError,
    LLMServiceError,
    SessionNotFoundError,
)
from src.domain.interfaces.llm_service import LLMService
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    SessionStore,
)
from src.infrastructure.logging import bind_context, clear_context

logger = logging.getLogger(__name__)


@dataclass
class ProcessMessageResult:
    """Result of ProcessMessage use case.

    Attributes:
        response: Generated LLM response text.
        user_message: Saved user message entity.
        assistant_message: Saved assistant message entity.
    """

    response: str
    user_message: Message
    assistant_message: Message


class ProcessMessage:
    """Use case for processing user messages and generating responses.

    Coordinates message validation, context building, LLM generation,
    and message persistence based on memory mode configuration.
    """

    def __init__(
        self,
        message_repo: MessageRepository,
        session_repo: SessionRepository,
        short_term_store: SessionStore,
        context_builder: ContextBuilder,
        llm_service: LLMService,
        default_model: str = "llama3",
        llm_timeout: float = 60.0,
    ) -> None:
        """Initialize ProcessMessage use case.

        Args:
            message_repo: Repository for long-term message storage.
            session_repo: Repository for session management.
            short_term_store: Store for short-term in-memory messages.
            context_builder: Service for building conversation context.
            llm_service: LLM service for generating responses.
            default_model: Default model name for LLM generation.
            llm_timeout: Timeout for LLM generation in seconds.
        """
        self._message_repo = message_repo
        self._session_repo = session_repo
        self._short_term_store = short_term_store
        self._context_builder = context_builder
        self._llm_service = llm_service
        self._default_model = default_model
        self._llm_timeout = llm_timeout

    async def execute(
        self,
        session_id: int,
        user_text: str,
        mode: Optional[MemoryMode] = None,
    ) -> ProcessMessageResult:
        """Process a user message and generate an LLM response.

        Args:
            session_id: Session identifier.
            user_text: User message text.
            mode: Optional memory mode override. If None, uses session's mode.

        Returns:
            ProcessMessageResult with response and saved messages.

        Raises:
            InvalidDataError: If session_id is not positive or user_text is empty.
            SessionNotFoundError: If session does not exist.
            LLMServiceError: If LLM service fails to generate response.
        """
        self._validate_input(session_id, user_text)

        # Bind context for structured logging
        bind_context(session_id=session_id)

        try:
            session = await self._get_session(session_id)
            bind_context(user_id=session.user_id)  # Update with real user_id

            logger.info(
                "Processing message: user_text_length=%d, memory_mode=%s",
                len(user_text),
                session.memory_mode.value,
            )

            effective_mode = mode if mode is not None else session.memory_mode

            context = await self._context_builder.build_context(
                session_id=session_id,
                mode=effective_mode,
            )

            user_message = self._create_user_message(
                session_id=session_id,
                content=user_text,
                memory_mode=effective_mode,
            )

            # Обработка исключений LLM с логированием
            try:
                # Добавляем таймаут для предотвращения hanging connections
                # Таймаут берётся из конфигурации (llm_timeout)
                async with asyncio.timeout(self._llm_timeout):
                    llm_response = await self._llm_service.generate(
                        prompt=user_text,
                        context=context,
                        model_params={"model": self._default_model},
                    )
            except asyncio.TimeoutError:
                logger.error(
                    "LLM generation timeout (%.1fs limit exceeded)",
                    self._llm_timeout,
                )
                raise LLMServiceError(
                    f"Generation timed out ({self._llm_timeout}s limit exceeded)"
                )
            except LLMServiceError:
                # Переподнимаем доменные исключения как есть
                raise
            except Exception as e:
                # Не перехватываем системные исключения
                if isinstance(e, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
                    raise
                logger.exception(
                    "LLM generation failed: error_type=%s",
                    type(e).__name__,
                )
                raise LLMServiceError(f"Failed to generate response: {e}")

            assistant_message = self._create_assistant_message(
                session_id=session_id,
                content=llm_response,
                memory_mode=effective_mode,
                model_used=self._default_model,
            )

            # Сохраняем и получаем сообщения с реальными ID
            user_message, assistant_message = await self._save_messages(
                user_message=user_message,
                assistant_message=assistant_message,
                mode=effective_mode,
            )

            logger.info(
                "Message processed: response_length=%d, model_used=%s",
                len(llm_response),
                self._default_model,
            )

            return ProcessMessageResult(
                response=llm_response,
                user_message=user_message,
                assistant_message=assistant_message,
            )

        finally:
            # Clean up logging context
            clear_context()

    def _validate_input(self, session_id: int, user_text: str) -> None:
        """Validate use case input parameters.

        Args:
            session_id: Session identifier to validate.
            user_text: User message text to validate.

        Raises:
            InvalidDataError: If validation fails.
        """
        if session_id <= 0:
            raise InvalidDataError(
                f"session_id must be positive, got {session_id}"
            )
        if not user_text or not user_text.strip():
            raise InvalidDataError("user_text cannot be empty")

    async def _get_session(self, session_id: int) -> Session:
        """Get session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session entity.

        Raises:
            SessionNotFoundError: If session does not exist.
        """
        session = await self._session_repo.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def _create_user_message(
        self,
        session_id: int,
        content: str,
        memory_mode: MemoryMode,
    ) -> Message:
        """Create user message entity.

        Args:
            session_id: Session identifier.
            content: Message content.
            memory_mode: Current memory mode.

        Returns:
            User message entity with message_id=0 (to be assigned by repo).
        """
        return Message(
            message_id=0,
            session_id=session_id,
            role="user",
            content=content,
            timestamp=datetime.now(timezone.utc),
            memory_mode_at_time=memory_mode,
        )

    def _create_assistant_message(
        self,
        session_id: int,
        content: str,
        memory_mode: MemoryMode,
        model_used: str,
    ) -> Message:
        """Create assistant message entity.

        Args:
            session_id: Session identifier.
            content: Message content (LLM response).
            memory_mode: Current memory mode.
            model_used: Model name used for generation.

        Returns:
            Assistant message entity with message_id=0.
        """
        return Message(
            message_id=0,
            session_id=session_id,
            role="assistant",
            content=content,
            timestamp=datetime.now(timezone.utc),
            model_used=model_used,
            memory_mode_at_time=memory_mode,
        )

    async def _save_messages(
        self,
        user_message: Message,
        assistant_message: Message,
        mode: MemoryMode,
    ) -> tuple[Message, Message]:
        """Save messages based on memory mode.

        Args:
            user_message: User message entity to save.
            assistant_message: Assistant message entity to save.
            mode: Memory mode determining storage strategy.

        Returns:
            Tuple of (user_message, assistant_message) with assigned IDs.

        Memory Mode Behavior:
            - NO_MEMORY: Messages are NOT saved.
            - SHORT_TERM: Save to short-term store only.
            - LONG_TERM: Save to long-term repo only.
            - BOTH: Save to both stores.
        """
        if mode == MemoryMode.NO_MEMORY:
            return user_message, assistant_message

        if mode in (MemoryMode.SHORT_TERM, MemoryMode.BOTH):
            # Get session for user_id (required by in-memory store)
            session = await self._session_repo.get(session_id=user_message.session_id)
            # Save to short-term and get messages with assigned IDs
            user_message, assistant_message = await self._save_to_short_term(
                user_message, assistant_message, session
            )

        if mode in (MemoryMode.LONG_TERM, MemoryMode.BOTH):
            # Сохраняем в БД и получаем сообщения с реальными ID
            user_message, assistant_message = (
                await self._save_to_long_term_with_ids(
                    user_message, assistant_message
                )
            )

        return user_message, assistant_message

    async def _save_to_short_term(
        self,
        user_message: Message,
        assistant_message: Message,
        session: Session,
    ) -> tuple[Message, Message]:
        """Save messages to short-term in-memory store and return with assigned IDs.

        Args:
            user_message: User message entity.
            assistant_message: Assistant message entity.
            session: Session entity with user_id for in-memory store.

        Returns:
            Tuple of (user_message, assistant_message) with assigned message IDs.
        """
        user_id = await self._short_term_store.add_message(
            session_id=user_message.session_id,
            message=user_message,
            session=session,
        )
        user_message_with_id = Message(
            message_id=user_id,
            session_id=user_message.session_id,
            role=user_message.role,
            content=user_message.content,
            timestamp=user_message.timestamp,
            memory_mode_at_time=user_message.memory_mode_at_time,
        )
        
        assistant_id = await self._short_term_store.add_message(
            session_id=assistant_message.session_id,
            message=assistant_message,
            session=session,
        )
        assistant_message_with_id = Message(
            message_id=assistant_id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            timestamp=assistant_message.timestamp,
            model_used=assistant_message.model_used,
            memory_mode_at_time=assistant_message.memory_mode_at_time,
        )
        
        return user_message_with_id, assistant_message_with_id

    async def _save_to_long_term_with_ids(
        self,
        user_message: Message,
        assistant_message: Message,
    ) -> tuple[Message, Message]:
        """Save messages to long-term database and return with assigned IDs.

        Args:
            user_message: User message entity.
            assistant_message: Assistant message entity.

        Returns:
            Tuple of (user_message, assistant_message) with assigned message_id.
        """
        # Сохраняем user message и получаем с ID
        user_id = await self._message_repo.add(user_message)
        user_message = Message(
            message_id=user_id,
            session_id=user_message.session_id,
            role=user_message.role,
            content=user_message.content,
            timestamp=user_message.timestamp,
            memory_mode_at_time=user_message.memory_mode_at_time,
        )

        # Сохраняем assistant message и получаем с ID
        assistant_id = await self._message_repo.add(assistant_message)
        assistant_message = Message(
            message_id=assistant_id,
            session_id=assistant_message.session_id,
            role=assistant_message.role,
            content=assistant_message.content,
            timestamp=assistant_message.timestamp,
            model_used=assistant_message.model_used,
            memory_mode_at_time=assistant_message.memory_mode_at_time,
        )

        return user_message, assistant_message

    async def _save_to_long_term(
        self,
        user_message: Message,
        assistant_message: Message,
    ) -> None:
        """Save messages to long-term database repository.

        Args:
            user_message: User message entity.
            assistant_message: Assistant message entity.
        """
        await self._message_repo.add(user_message)
        await self._message_repo.add(assistant_message)
