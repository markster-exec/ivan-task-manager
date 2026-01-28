"""Tests for source writers."""

import pytest
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
    """Test that writer stubs implement the interface."""

    def test_clickup_writer_is_source_writer(self):
        """ClickUpWriter is a SourceWriter subclass."""
        writer = ClickUpWriter()
        assert isinstance(writer, SourceWriter)

    def test_github_writer_is_source_writer(self):
        """GitHubWriter is a SourceWriter subclass."""
        writer = GitHubWriter()
        assert isinstance(writer, SourceWriter)

    @pytest.mark.asyncio
    async def test_clickup_complete_not_implemented(self):
        """ClickUpWriter.complete raises NotImplementedError (stub)."""
        writer = ClickUpWriter()
        with pytest.raises(NotImplementedError):
            await writer.complete("123")

    @pytest.mark.asyncio
    async def test_github_complete_not_implemented(self):
        """GitHubWriter.complete raises NotImplementedError (stub)."""
        writer = GitHubWriter()
        with pytest.raises(NotImplementedError):
            await writer.complete("456")
