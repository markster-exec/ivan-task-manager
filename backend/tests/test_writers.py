"""Tests for source writers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.writers.base import WriteResult, SourceWriter
from app.writers import get_writer, ClickUpWriter, GitHubWriter


class TestWriteResult:
    """Test WriteResult dataclass."""

    def test_success_result(self):
        """WriteResult with success=True."""
        result = WriteResult(success=True, message="Done")
        assert result.success is True
        assert result.message == "Done"
        assert result.source_id is None
        assert result.conflict is False

    def test_failure_result(self):
        """WriteResult with success=False."""
        result = WriteResult(success=False, message="Failed")
        assert result.success is False
        assert result.message == "Failed"

    def test_conflict_result(self):
        """WriteResult with conflict detected."""
        result = WriteResult(
            success=True,
            message="Already done",
            conflict=True,
            current_state="closed",
        )
        assert result.success is True
        assert result.conflict is True
        assert result.current_state == "closed"

    def test_create_result_with_source_id(self):
        """WriteResult from create includes source_id."""
        result = WriteResult(
            success=True,
            message="Created",
            source_id="abc123",
        )
        assert result.source_id == "abc123"


class TestGetWriter:
    """Test get_writer factory function."""

    def test_get_clickup_writer(self):
        """get_writer returns ClickUpWriter for 'clickup'."""
        writer = get_writer("clickup")
        assert isinstance(writer, ClickUpWriter)
        assert isinstance(writer, SourceWriter)

    def test_get_github_writer(self):
        """get_writer returns GitHubWriter for 'github'."""
        writer = get_writer("github")
        assert isinstance(writer, GitHubWriter)
        assert isinstance(writer, SourceWriter)

    def test_unknown_source_raises(self):
        """get_writer raises ValueError for unknown source."""
        with pytest.raises(ValueError, match="Unknown source"):
            get_writer("jira")  # type: ignore


class TestSourceWriterInterface:
    """Test that writers implement the interface."""

    def test_clickup_writer_is_source_writer(self):
        """ClickUpWriter is a SourceWriter subclass."""
        writer = ClickUpWriter()
        assert isinstance(writer, SourceWriter)

    def test_github_writer_is_source_writer(self):
        """GitHubWriter is a SourceWriter subclass."""
        writer = GitHubWriter()
        assert isinstance(writer, SourceWriter)

    @pytest.mark.asyncio
    async def test_github_complete_not_implemented(self):
        """GitHubWriter.complete raises NotImplementedError (stub)."""
        writer = GitHubWriter()
        with pytest.raises(NotImplementedError):
            await writer.complete("456")


class TestClickUpWriter:
    """Test ClickUpWriter."""

    @pytest.fixture
    def writer(self):
        """Create ClickUpWriter with mocked settings."""
        with patch("app.writers.clickup.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                clickup_api_token="test-token",
                clickup_list_id="test-list",
                clickup_complete_status="complete",
            )
            return ClickUpWriter()

    @pytest.mark.asyncio
    async def test_complete_success(self, writer):
        """Complete marks task as complete in ClickUp."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": {"status": "to do"}}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            client.put.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is True
            assert "ClickUp" in result.message
            client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_already_done(self, writer):
        """Complete detects already-completed task."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": {"status": "complete"}}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is True
            assert result.conflict is True
            client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_http_error(self, writer):
        """Complete handles HTTP errors gracefully."""
        with patch.object(writer, "_get_client") as mock_client:
            client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 404
            client.get.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=error_response
            )
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is False
            assert "404" in result.message

    @pytest.mark.asyncio
    async def test_comment_success(self, writer):
        """Comment adds comment to task."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.comment("abc123", "Test comment")

            assert result.success is True
            client.post.assert_called_once()
            call_args = client.post.call_args
            assert "comment" in call_args[0][0]
            assert call_args[1]["json"]["comment_text"] == "Test comment"

    @pytest.mark.asyncio
    async def test_create_success(self, writer):
        """Create creates task in ClickUp."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "new-task-id"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Task", description="Test desc")

            assert result.success is True
            assert result.source_id == "new-task-id"

    @pytest.mark.asyncio
    async def test_create_with_entity_tag(self, writer):
        """Create adds entity tag when entity_id provided."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "new-task-id"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Task", entity_id="mark-smith")

            assert result.success is True
            call_args = client.post.call_args
            assert call_args[1]["json"]["tags"] == ["client:mark-smith"]
