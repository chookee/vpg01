"""Tests for ExportHistory and ImportHistory use cases.

This module contains unit tests for history export/import functionality.

Run: pytest tests/unit/test_export_import.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.application.use_cases.export_history import ExportHistory, ExportHistoryError
from src.application.use_cases.import_history import (
    ImportHistory,
    ImportHistoryError,
    ImportHistoryResult,
)
from src.domain.entities.message import Message
from src.domain.entities.session import Session
from src.domain.enums import MemoryMode
from src.domain.exceptions import InvalidDataError, SessionNotFoundError


@pytest.fixture
def mock_repositories():
    """Create mock repositories for testing."""
    message_repo = AsyncMock()
    session_repo = AsyncMock()
    short_term_store = AsyncMock()
    return {
        "message_repo": message_repo,
        "session_repo": session_repo,
        "short_term_store": short_term_store,
    }


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    return Session(
        session_id=1,
        user_id=1,
        memory_mode=MemoryMode.SHORT_TERM,
    )


@pytest.fixture
def sample_messages():
    """Create sample messages for testing."""
    from datetime import datetime, timezone

    return [
        Message(
            message_id=1,
            session_id=1,
            role="user",
            content="Hello",
            timestamp=datetime.now(timezone.utc),
        ),
        Message(
            message_id=2,
            session_id=1,
            role="assistant",
            content="Hi there!",
            timestamp=datetime.now(timezone.utc),
        ),
    ]


class TestExportHistory:
    """Tests for ExportHistory use case."""

    @pytest.mark.asyncio
    async def test_export_success(self, mock_repositories, sample_session, sample_messages):
        """Test successful history export."""
        # Setup mocks
        mock_repositories["session_repo"].get.return_value = sample_session
        mock_repositories["message_repo"].get_by_session.return_value = sample_messages
        mock_repositories["short_term_store"].get_messages.return_value = []

        # Create use case
        exporter = ExportHistory(**mock_repositories)

        # Execute
        result = await exporter.execute(session_id=1)

        # Verify
        assert isinstance(result, str)
        data = json.loads(result)
        assert "version" in data
        assert data["version"] == "1.0"
        assert "messages" in data
        assert data["message_count"] == 2

    @pytest.mark.asyncio
    async def test_export_invalid_session_id(self, mock_repositories):
        """Test export with invalid session ID."""
        exporter = ExportHistory(**mock_repositories)

        with pytest.raises(InvalidDataError):
            await exporter.execute(session_id=-1)

    @pytest.mark.asyncio
    async def test_export_session_not_found(self, mock_repositories):
        """Test export when session doesn't exist."""
        mock_repositories["session_repo"].get.return_value = None

        exporter = ExportHistory(**mock_repositories)

        with pytest.raises(SessionNotFoundError):
            await exporter.execute(session_id=999)

    @pytest.mark.asyncio
    async def test_export_empty_history(self, mock_repositories, sample_session):
        """Test export with empty history."""
        mock_repositories["session_repo"].get.return_value = sample_session
        mock_repositories["message_repo"].get_by_session.return_value = []
        mock_repositories["short_term_store"].get_messages.return_value = []

        exporter = ExportHistory(**mock_repositories)
        result = await exporter.execute(session_id=1)

        data = json.loads(result)
        assert data["message_count"] == 0


class TestImportHistory:
    """Tests for ImportHistory use case."""

    @pytest.mark.asyncio
    async def test_import_success(self, mock_repositories, sample_session):
        """Test successful history import."""
        # Create export data
        export_data = {
            "version": "1.0",
            "exported_at": "2024-01-01T00:00:00Z",
            "session": {
                "session_id": 1,
                "user_id": 1,
                "memory_mode": "short_term",
                "created_at": "2024-01-01T00:00:00Z",
                "last_activity": "2024-01-01T00:00:00Z",
            },
            "message_count": 2,
            "messages": [
                {
                    "message_id": 100,
                    "session_id": 1,
                    "role": "user",
                    "content": "Test message",
                    "timestamp": "2024-01-01T00:00:00Z",
                    "model_used": None,
                    "memory_mode_at_time": "short_term",
                }
            ],
        }

        # Setup mocks
        mock_repositories["session_repo"].get.return_value = sample_session
        mock_repositories["message_repo"].get_by_session.return_value = []

        importer = ImportHistory(**mock_repositories)
        result = await importer.execute(session_id=1, json_data=json.dumps(export_data))

        assert result.imported_count == 1
        assert result.skipped_count == 0
        mock_repositories["message_repo"].add.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_invalid_json(self, mock_repositories, sample_session):
        """Test import with invalid JSON."""
        mock_repositories["session_repo"].get.return_value = sample_session

        importer = ImportHistory(**mock_repositories)

        with pytest.raises(ImportHistoryError):
            await importer.execute(session_id=1, json_data="not valid json")

    @pytest.mark.asyncio
    async def test_import_unsupported_version(self, mock_repositories, sample_session):
        """Test import with unsupported export version."""
        export_data = {
            "version": "99.0",  # Unsupported version
            "messages": [],
        }

        mock_repositories["session_repo"].get.return_value = sample_session

        importer = ImportHistory(**mock_repositories)

        with pytest.raises(ImportHistoryError, match="Unsupported export version"):
            await importer.execute(session_id=1, json_data=json.dumps(export_data))

    @pytest.mark.asyncio
    async def test_import_skip_duplicates(
        self, mock_repositories, sample_session, sample_messages
    ):
        """Test that duplicate messages are skipped."""
        export_data = {
            "version": "1.0",
            "exported_at": "2024-01-01T00:00:00Z",
            "session": {
                "session_id": 1,
                "user_id": 1,
                "memory_mode": "short_term",
            },
            "message_count": 1,
            "messages": [
                {
                    "message_id": 1,  # Same as existing
                    "session_id": 1,
                    "role": "user",
                    "content": "Duplicate",
                    "timestamp": "2024-01-01T00:00:00Z",
                }
            ],
        }

        # Setup mocks - session already has message with id=1
        mock_repositories["session_repo"].get.return_value = sample_session
        mock_repositories["message_repo"].get_by_session.return_value = sample_messages

        importer = ImportHistory(**mock_repositories)
        result = await importer.execute(session_id=1, json_data=json.dumps(export_data))

        assert result.imported_count == 0
        assert result.skipped_count == 1

    @pytest.mark.asyncio
    async def test_import_invalid_session_id(self, mock_repositories):
        """Test import with invalid session ID."""
        importer = ImportHistory(**mock_repositories)

        with pytest.raises(InvalidDataError):
            await importer.execute(session_id=-1, json_data="{}")

    @pytest.mark.asyncio
    async def test_import_empty_json_data(self, mock_repositories):
        """Test import with empty JSON data."""
        importer = ImportHistory(**mock_repositories)

        with pytest.raises(InvalidDataError, match="json_data cannot be empty"):
            await importer.execute(session_id=1, json_data="")


class TestImportHistoryResult:
    """Tests for ImportHistoryResult class."""

    def test_result_str_representation(self):
        """Test string representation of import result."""
        result = ImportHistoryResult(
            imported_count=5,
            skipped_count=2,
            errors=["error1", "error2"],
        )

        result_str = str(result)
        assert "Imported: 5" in result_str
        assert "Skipped: 2" in result_str
        assert "Errors: 2" in result_str

    def test_result_no_errors(self):
        """Test result with no errors."""
        result = ImportHistoryResult(imported_count=3, skipped_count=1)

        result_str = str(result)
        assert "Errors" not in result_str
