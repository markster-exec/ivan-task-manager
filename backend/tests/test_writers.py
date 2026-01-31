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


class TestGitHubWriter:
    """Test GitHubWriter."""

    @pytest.fixture
    def writer(self):
        """Create GitHubWriter with mocked settings."""
        with patch("app.writers.github.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                github_token="test-token",
                github_repo="test-owner/test-repo",
            )
            return GitHubWriter()

    @pytest.mark.asyncio
    async def test_complete_success(self, writer):
        """Complete closes issue in GitHub."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_get_response = MagicMock()
            mock_get_response.json.return_value = {"state": "open"}
            mock_get_response.raise_for_status = MagicMock()

            mock_patch_response = MagicMock()
            mock_patch_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_get_response
            client.patch.return_value = mock_patch_response
            mock_client.return_value = client

            result = await writer.complete("123")

            assert result.success is True
            assert "GitHub" in result.message
            client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_already_closed(self, writer):
        """Complete detects already-closed issue."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"state": "closed"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("123")

            assert result.success is True
            assert result.conflict is True
            assert result.current_state == "closed"
            client.patch.assert_not_called()

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

            result = await writer.complete("123")

            assert result.success is False
            assert "404" in result.message

    @pytest.mark.asyncio
    async def test_comment_success(self, writer):
        """Comment adds comment to issue."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.comment("123", "Test comment")

            assert result.success is True
            client.post.assert_called_once()
            call_args = client.post.call_args
            assert "comments" in call_args[0][0]
            assert call_args[1]["json"]["body"] == "Test comment"

    @pytest.mark.asyncio
    async def test_create_success(self, writer):
        """Create creates issue in GitHub."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"number": 456}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Issue", description="Test body")

            assert result.success is True
            assert result.source_id == "456"

    @pytest.mark.asyncio
    async def test_create_with_entity_tag(self, writer):
        """Create prepends entity tag to title when entity_id provided."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"number": 789}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Issue", entity_id="acme-corp")

            assert result.success is True
            call_args = client.post.call_args
            assert call_args[1]["json"]["title"] == "[CLIENT:acme-corp] Test Issue"

    @pytest.mark.asyncio
    async def test_update_due_date_adds_comment(self, writer):
        """update_due_date adds comment since GitHub has no native due dates."""
        from datetime import date

        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            new_date = date(2026, 2, 15)
            result = await writer.update_due_date("123", new_date)

            assert result.success is True
            client.post.assert_called_once()
            call_args = client.post.call_args
            assert "comments" in call_args[0][0]
            assert "2026-02-15" in call_args[1]["json"]["body"]

    @pytest.mark.asyncio
    async def test_reassign_success(self, writer):
        """reassign updates issue assignees."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.patch.return_value = mock_response
            mock_client.return_value = client

            result = await writer.reassign("123", "atiti")

            assert result.success is True
            assert "atiti" in result.message
            client.patch.assert_called_once()
            call_args = client.patch.call_args
            assert call_args[1]["json"]["assignees"] == ["atiti"]

    @pytest.mark.asyncio
    async def test_reassign_not_collaborator(self, writer):
        """reassign handles 422 error for non-collaborators."""
        with patch.object(writer, "_get_client") as mock_client:
            client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 422
            client.patch.side_effect = httpx.HTTPStatusError(
                "Unprocessable", request=MagicMock(), response=error_response
            )
            mock_client.return_value = client

            result = await writer.reassign("123", "unknown-user")

            assert result.success is False
            assert "not a collaborator" in result.message


class TestClickUpWriterNewMethods:
    """Test new ClickUpWriter methods: update_due_date and reassign."""

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
    async def test_update_due_date_success(self, writer):
        """update_due_date updates task due date in ClickUp."""
        from datetime import date

        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.put.return_value = mock_response
            mock_client.return_value = client

            new_date = date(2026, 2, 15)
            result = await writer.update_due_date("abc123", new_date)

            assert result.success is True
            assert "2026-02-15" in result.message
            client.put.assert_called_once()
            call_args = client.put.call_args
            assert "due_date" in call_args[1]["json"]

    @pytest.mark.asyncio
    async def test_update_due_date_http_error(self, writer):
        """update_due_date handles HTTP errors."""
        from datetime import date

        with patch.object(writer, "_get_client") as mock_client:
            client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 500
            client.put.side_effect = httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=error_response
            )
            mock_client.return_value = client

            result = await writer.update_due_date("abc123", date(2026, 2, 15))

            assert result.success is False
            assert "500" in result.message

    @pytest.mark.asyncio
    async def test_reassign_success(self, writer):
        """reassign updates task assignees in ClickUp."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_get_response = MagicMock()
            mock_get_response.json.return_value = {
                "assignees": [{"id": "old-assignee"}]
            }
            mock_get_response.raise_for_status = MagicMock()

            mock_put_response = MagicMock()
            mock_put_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_get_response
            client.put.return_value = mock_put_response
            mock_client.return_value = client

            result = await writer.reassign("abc123", "new-assignee-id")

            assert result.success is True
            assert "reassigned" in result.message.lower()
            client.put.assert_called_once()
            call_args = client.put.call_args
            assert call_args[1]["json"]["assignees"]["rem"] == ["old-assignee"]
            assert call_args[1]["json"]["assignees"]["add"] == ["new-assignee-id"]

    @pytest.mark.asyncio
    async def test_reassign_http_error(self, writer):
        """reassign handles HTTP errors."""
        with patch.object(writer, "_get_client") as mock_client:
            client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 403
            client.get.side_effect = httpx.HTTPStatusError(
                "Forbidden", request=MagicMock(), response=error_response
            )
            mock_client.return_value = client

            result = await writer.reassign("abc123", "assignee-id")

            assert result.success is False
            assert "403" in result.message
