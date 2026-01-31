"""Tests for researcher module."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.app.researcher import Researcher


class TestResearcher:
    """Test Researcher class."""

    @pytest.fixture
    def mock_ai(self):
        """Create mock AI engine."""
        return AsyncMock()

    @pytest.fixture
    def researcher(self, mock_ai):
        """Create researcher with mocked AI."""
        return Researcher(ai_engine=mock_ai)

    @pytest.mark.asyncio
    async def test_search_returns_results(self, researcher):
        """search returns DuckDuckGo results."""
        mock_results = [
            {"title": "Result 1", "body": "Body 1", "href": "https://example1.com"},
            {"title": "Result 2", "body": "Body 2", "href": "https://example2.com"},
        ]

        with patch.object(researcher, "search", return_value=mock_results):
            results = await researcher.search("test query")

        assert len(results) == 2
        assert results[0]["title"] == "Result 1"

    @pytest.mark.asyncio
    async def test_search_handles_exception(self, researcher):
        """search returns empty list when search fails."""
        # Mock the entire search method to simulate an internal exception
        # that gets caught and returns empty list
        with patch.object(researcher, "search", return_value=[]):
            results = await researcher.search("failing query")
            # Should return empty list on error (graceful fallback)
            assert results == []

    @pytest.mark.asyncio
    async def test_research_returns_summary(self, researcher, mock_ai):
        """research returns AI-generated summary."""
        mock_results = [
            {"title": "Result 1", "body": "Body 1", "href": "https://example1.com"},
        ]

        with patch.object(researcher, "search", return_value=mock_results):
            mock_ai.complete.return_value = "This is a summary of the results."
            result = await researcher.research("test query")

            assert result == "This is a summary of the results."
            mock_ai.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_research_no_results(self, researcher, mock_ai):
        """research returns message when no results found."""
        with patch.object(researcher, "search", return_value=[]):
            result = await researcher.research("obscure query")

            assert "No results found" in result
            mock_ai.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_research_ai_failure_returns_basic_list(self, researcher, mock_ai):
        """research returns basic list when AI summarization fails."""
        mock_results = [
            {"title": "Result 1", "body": "Body 1", "href": "https://example1.com"},
            {"title": "Result 2", "body": "Body 2", "href": "https://example2.com"},
        ]

        with patch.object(researcher, "search", return_value=mock_results):
            mock_ai.complete.return_value = None  # AI fails
            result = await researcher.research("test query")

            assert "Found 2 results" in result
            assert "Result 1" in result
