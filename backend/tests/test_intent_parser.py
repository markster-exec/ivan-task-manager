"""Tests for intent parser."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.app.intent_parser import (
    IntentParser,
    ParsedIntent,
    _parse_date_to_days,
)


class TestParseDateToDays:
    """Test date parsing helper."""

    def test_parse_days(self):
        """Parses '3 days' to 3."""
        assert _parse_date_to_days("3 days") == 3

    def test_parse_day_singular(self):
        """Parses '1 day' to 1."""
        assert _parse_date_to_days("1 day") == 1

    def test_parse_weeks(self):
        """Parses '2 weeks' to 14."""
        assert _parse_date_to_days("2 weeks") == 14

    def test_parse_tomorrow(self):
        """Parses 'tomorrow' to 1."""
        assert _parse_date_to_days("tomorrow") == 1

    def test_parse_next_week(self):
        """Parses 'next week' to 7."""
        assert _parse_date_to_days("next week") == 7

    def test_parse_monday(self):
        """Parses 'monday' to days until next Monday."""
        days = _parse_date_to_days("monday")
        assert days is not None
        assert 1 <= days <= 7

    def test_parse_unknown_returns_none(self):
        """Returns None for unknown date format."""
        assert _parse_date_to_days("sometime") is None


class TestParsedIntent:
    """Test ParsedIntent dataclass."""

    def test_default_values(self):
        """ParsedIntent has sensible defaults."""
        intent = ParsedIntent(intent="next")
        assert intent.intent == "next"
        assert intent.params == {}
        assert intent.confidence == 1.0
        assert intent.raw_text == ""

    def test_with_params(self):
        """ParsedIntent stores params."""
        intent = ParsedIntent(
            intent="defer",
            params={"entity": "kyle", "days": 7},
            confidence=0.8,
            raw_text="defer kyle to next week",
        )
        assert intent.params["entity"] == "kyle"
        assert intent.params["days"] == 7


class TestIntentParserRegex:
    """Test regex-based intent parsing."""

    @pytest.fixture
    def parser(self):
        """Create parser with mocked AI engine."""
        mock_ai = MagicMock()
        return IntentParser(ai_engine=mock_ai)

    def test_parse_next(self, parser):
        """Parses 'next' command."""
        result = parser._try_regex("next")
        assert result is not None
        assert result.intent == "next"
        assert result.confidence == 1.0

    def test_parse_what_should_i_do(self, parser):
        """Parses 'what should i do' as next."""
        result = parser._try_regex("what should i do")
        assert result is not None
        assert result.intent == "next"

    def test_parse_done(self, parser):
        """Parses 'done' command."""
        result = parser._try_regex("done")
        assert result is not None
        assert result.intent == "done"

    def test_parse_finished(self, parser):
        """Parses 'finished' as done."""
        result = parser._try_regex("finished")
        assert result is not None
        assert result.intent == "done"

    def test_parse_skip(self, parser):
        """Parses 'skip' command."""
        result = parser._try_regex("skip")
        assert result is not None
        assert result.intent == "skip"

    def test_parse_tasks(self, parser):
        """Parses 'tasks' command."""
        result = parser._try_regex("tasks")
        assert result is not None
        assert result.intent == "tasks"

    def test_parse_show_my_tasks(self, parser):
        """Parses 'show my tasks' as tasks."""
        result = parser._try_regex("show my tasks")
        assert result is not None
        assert result.intent == "tasks"

    def test_parse_help(self, parser):
        """Parses 'help' command."""
        result = parser._try_regex("help")
        assert result is not None
        assert result.intent == "help"

    def test_parse_entity_query(self, parser):
        """Parses entity query."""
        result = parser._try_regex("what's happening with kyle")
        assert result is not None
        assert result.intent == "entity_query"
        assert result.params["entity_name"] == "kyle"

    def test_parse_research_query(self, parser):
        """Parses research query."""
        result = parser._try_regex("find coworking spaces in LA")
        assert result is not None
        assert result.intent == "research"
        # Query is lowercased during regex matching
        assert "coworking spaces in la" in result.params["query"]

    def test_parse_unknown_returns_none(self, parser):
        """Returns None for unrecognized input."""
        result = parser._try_regex("something random and complex")
        assert result is None


class TestIntentParserAI:
    """Test AI-based intent parsing."""

    @pytest.fixture
    def mock_ai(self):
        """Create mock AI engine."""
        return AsyncMock()

    @pytest.fixture
    def parser(self, mock_ai):
        """Create parser with mocked AI engine."""
        return IntentParser(ai_engine=mock_ai)

    @pytest.mark.asyncio
    async def test_parse_uses_regex_first(self, parser, mock_ai):
        """Parse uses regex before AI for known commands."""
        result = await parser.parse("next")

        assert result.intent == "next"
        mock_ai.complete_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_parse_falls_back_to_ai(self, parser, mock_ai):
        """Parse falls back to AI for complex queries."""
        mock_ai.complete_json.return_value = {
            "intent": "defer",
            "params": {"entity": "kyle", "days": 7},
            "confidence": 0.85,
        }

        result = await parser.parse("push all kyle stuff to next week")

        assert result.intent == "defer"
        assert result.params["entity"] == "kyle"
        mock_ai.complete_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_returns_unknown_when_ai_fails(self, parser, mock_ai):
        """Parse returns unknown when AI returns None."""
        mock_ai.complete_json.return_value = None

        result = await parser.parse("something completely random")

        assert result.intent == "unknown"
        assert result.confidence == 0.0
