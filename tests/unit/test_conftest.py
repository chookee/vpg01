"""Tests for pytest fixtures and conftest configuration."""

import pytest

from src.domain.enums import MemoryMode


@pytest.mark.unit
class TestFixtures:
    """Test that conftest fixtures work correctly."""

    def test_mock_message_repository(self, mock_message_repository) -> None:
        """Test mock message repository fixture."""
        assert mock_message_repository is not None
        assert hasattr(mock_message_repository, "add")
        assert hasattr(mock_message_repository, "get_by_session")

    def test_mock_session_repository(self, mock_session_repository) -> None:
        """Test mock session repository fixture."""
        assert mock_session_repository is not None
        assert hasattr(mock_session_repository, "create")
        assert hasattr(mock_session_repository, "get")

    def test_mock_user_repository(self, mock_user_repository) -> None:
        """Test mock user repository fixture."""
        assert mock_user_repository is not None
        assert hasattr(mock_user_repository, "create")
        assert hasattr(mock_user_repository, "get_by_id")

    def test_user_factory(self, user_factory) -> None:
        """Test user factory fixture."""
        user = user_factory()
        assert user.user_id == 1
        assert user.default_mode == MemoryMode.SHORT_TERM

        user_custom = user_factory(user_id=42, telegram_id=123456)
        assert user_custom.user_id == 42
        assert user_custom.telegram_id == 123456

    def test_session_factory(self, session_factory) -> None:
        """Test session factory fixture."""
        session = session_factory()
        assert session.session_id == 1
        assert session.user_id == 1

        session_custom = session_factory(
            session_id=100,
            user_id=42,
            memory_mode=MemoryMode.LONG_TERM,
        )
        assert session_custom.session_id == 100
        assert session_custom.user_id == 42
        assert session_custom.memory_mode == MemoryMode.LONG_TERM

    def test_message_factory(self, message_factory) -> None:
        """Test message factory fixture."""
        message = message_factory()
        assert message.message_id == 1
        assert message.session_id == 1
        assert message.role == "user"
        assert message.content == "Test message"

        message_custom = message_factory(
            message_id=42,
            session_id=10,
            role="assistant",
            content="Hello!",
            model_used="llama3",
        )
        assert message_custom.message_id == 42
        assert message_custom.session_id == 10
        assert message_custom.role == "assistant"
        assert message_custom.content == "Hello!"
        assert message_custom.model_used == "llama3"
