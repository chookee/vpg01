"""Tests for domain interfaces (Milestone 3)."""

import inspect
from typing import Protocol, get_origin

import pytest

from src.domain.interfaces.llm_service import LLMService, LLMServiceError
from src.domain.interfaces.logger import Logger
from src.domain.interfaces.repositories import (
    MessageRepository,
    SessionRepository,
    UserRepository,
)


def _is_protocol(cls: type) -> bool:
    """Check if a class is a Protocol."""
    return get_origin(cls) is Protocol or hasattr(cls, "_is_protocol") and cls._is_protocol  # type: ignore[attr-defined]


class TestMessageRepository:
    """Tests for MessageRepository protocol."""

    def test_message_repository_is_protocol(self) -> None:
        """MessageRepository should be a Protocol."""
        assert _is_protocol(MessageRepository)

    def test_message_repository_has_required_methods(self) -> None:
        """MessageRepository should have required abstract methods."""
        required_methods = {"add", "get_by_session", "update", "delete", "delete_by_session"}
        actual_methods = {
            name
            for name, method in inspect.getmembers(MessageRepository)
            if not name.startswith("_") and callable(method)
        }
        assert required_methods.issubset(actual_methods)


class TestSessionRepository:
    """Tests for SessionRepository protocol."""

    def test_session_repository_is_protocol(self) -> None:
        """SessionRepository should be a Protocol."""
        assert _is_protocol(SessionRepository)

    def test_session_repository_has_required_methods(self) -> None:
        """SessionRepository should have required abstract methods."""
        required_methods = {"create", "get", "update_mode", "delete"}
        actual_methods = {
            name
            for name, method in inspect.getmembers(SessionRepository)
            if not name.startswith("_") and callable(method)
        }
        assert required_methods.issubset(actual_methods)


class TestUserRepository:
    """Tests for UserRepository protocol."""

    def test_user_repository_is_protocol(self) -> None:
        """UserRepository should be a Protocol."""
        assert _is_protocol(UserRepository)

    def test_user_repository_has_required_methods(self) -> None:
        """UserRepository should have required abstract methods."""
        required_methods = {"create", "get_by_id", "get_by_telegram_id", "update"}
        actual_methods = {
            name
            for name, method in inspect.getmembers(UserRepository)
            if not name.startswith("_") and callable(method)
        }
        assert required_methods.issubset(actual_methods)


class TestLLMService:
    """Tests for LLMService abstract class."""

    def test_llm_service_is_abstract(self) -> None:
        """LLMService should be an ABC."""
        assert inspect.isabstract(LLMService)

    def test_llm_service_has_generate_method(self) -> None:
        """LLMService should have generate abstract method."""
        assert "generate" in dir(LLMService)
        method = getattr(LLMService, "generate")
        assert getattr(method, "__isabstractmethod__", False)

    def test_llm_service_error_is_exception(self) -> None:
        """LLMServiceError should be an Exception."""
        assert issubclass(LLMServiceError, Exception)

    def test_llm_service_cannot_be_instantiated(self) -> None:
        """LLMService cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMService()  # type: ignore[abstract]


class TestLogger:
    """Tests for Logger abstract class."""

    def test_logger_is_abstract(self) -> None:
        """Logger should be an ABC."""
        assert inspect.isabstract(Logger)

    def test_logger_has_required_methods(self) -> None:
        """Logger should have required abstract methods."""
        required_methods = {"info", "debug", "error", "warning"}
        actual_methods = {
            name
            for name, method in inspect.getmembers(Logger)
            if not name.startswith("_") and callable(method)
        }
        assert required_methods.issubset(actual_methods)

    def test_logger_cannot_be_instantiated(self) -> None:
        """Logger cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Logger()  # type: ignore[abstract]


class TestImports:
    """Tests for clean imports from domain package."""

    def test_import_from_domain(self) -> None:
        """Should be able to import interfaces from domain."""
        from src.domain import (
            LLMService,
            LLMServiceError,
            Logger,
            MemoryMode,
            MessageRepository,
            SessionRepository,
            UserRepository,
        )

        # Just check they are importable
        assert LLMService is not None
        assert Logger is not None
        assert MemoryMode is not None
        assert MessageRepository is not None
        assert SessionRepository is not None
        assert UserRepository is not None
        assert LLMServiceError is not None
