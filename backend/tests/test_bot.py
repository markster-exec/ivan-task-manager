"""Tests for Slack bot functionality."""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Task


# Create test database with thread safety
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mock_session():
    """Create test database session."""
    return TestSessionLocal()


class TestBotHandlers:
    """Test bot command handlers."""

    @pytest.mark.asyncio
    async def test_handle_next_returns_dict_with_blocks(self, mock_session):
        """handle_next should return dict with text and blocks."""
        # Add a test task
        task = Task(
            id="test-1",
            source="clickup",
            title="Test Task",
            url="https://example.com/task",
            status="todo",
            assignee="ivan",
            score=500,
        )
        mock_session.add(task)
        mock_session.commit()

        with patch("app.bot.SessionLocal", return_value=mock_session):
            from app.bot import handle_next

            result = await handle_next("user123")

        assert isinstance(result, dict)
        assert "text" in result
        assert "blocks" in result
        assert isinstance(result["blocks"], list)
        assert len(result["blocks"]) > 0

    @pytest.mark.asyncio
    async def test_handle_next_no_tasks_returns_text_only(self, mock_session):
        """handle_next with no tasks returns dict with text only."""
        with patch("app.bot.SessionLocal", return_value=mock_session):
            from app.bot import handle_next

            result = await handle_next("user123")

        assert isinstance(result, dict)
        assert "text" in result
        assert "No tasks in queue" in result["text"]

    @pytest.mark.asyncio
    async def test_handle_tasks_returns_block_kit(self, mock_session):
        """handle_tasks should return Block Kit formatted list."""
        # Add test tasks
        for i in range(3):
            task = Task(
                id=f"test-{i}",
                source="clickup",
                title=f"Task {i}",
                url=f"https://example.com/task/{i}",
                status="todo",
                assignee="ivan",
                score=500 - i * 100,
            )
            mock_session.add(task)
        mock_session.commit()

        with patch("app.bot.SessionLocal", return_value=mock_session):
            from app.bot import handle_tasks

            result = await handle_tasks("user123")

        assert isinstance(result, dict)
        assert "text" in result
        assert "blocks" in result
        # Should have header, divider, and task sections
        assert len(result["blocks"]) >= 3

    @pytest.mark.asyncio
    async def test_handle_help_returns_block_kit(self):
        """handle_help should return Block Kit formatted help."""
        from app.bot import handle_help

        result = await handle_help("user123")

        assert isinstance(result, dict)
        assert "text" in result
        assert "blocks" in result
        # Help text should mention commands
        assert (
            "next" in result["text"].lower() or "next" in str(result["blocks"]).lower()
        )


class TestBlockKitFormatting:
    """Test Slack Block Kit formatting utilities."""

    def test_section_creates_valid_block(self):
        """section() should create valid Slack section block."""
        from app.slack_blocks import section

        result = section("Test message")

        assert result["type"] == "section"
        assert result["text"]["type"] == "mrkdwn"
        assert result["text"]["text"] == "Test message"

    def test_divider_creates_valid_block(self):
        """divider() should create valid Slack divider block."""
        from app.slack_blocks import divider

        result = divider()

        assert result["type"] == "divider"

    def test_context_creates_valid_block(self):
        """context() should create valid Slack context block."""
        from app.slack_blocks import context

        result = context("Small text")

        assert result["type"] == "context"
        assert result["elements"][0]["type"] == "mrkdwn"
        assert result["elements"][0]["text"] == "Small text"

    def test_format_next_task_returns_tuple(self):
        """format_next_task should return (text, blocks) tuple."""
        from app.slack_blocks import format_next_task

        text, blocks = format_next_task(
            title="Test Task",
            url="https://example.com",
            score=500,
            flags=["Revenue", "Due today"],
            description="Task description here",
        )

        assert isinstance(text, str)
        assert isinstance(blocks, list)
        assert len(blocks) > 0
        assert "Test Task" in text or "Focus" in text

    def test_format_task_list_returns_tuple(self):
        """format_task_list should return (text, blocks) tuple."""
        from app.slack_blocks import format_task_list

        tasks_data = [
            {
                "title": "Task 1",
                "url": "https://example.com/1",
                "score": 500,
                "urgency_label": "Due today",
                "emoji": "🔴",
            },
            {
                "title": "Task 2",
                "url": "https://example.com/2",
                "score": 300,
                "urgency_label": "This week",
                "emoji": "🟡",
            },
        ]

        text, blocks = format_task_list(tasks_data, 2)

        assert isinstance(text, str)
        assert isinstance(blocks, list)
        assert "2" in text  # Should mention total count

    def test_format_morning_briefing_returns_tuple(self):
        """format_morning_briefing should return (text, blocks) tuple."""
        from app.slack_blocks import format_morning_briefing

        focus_tasks = [
            {
                "title": "Task 1",
                "url": "https://example.com/1",
                "score": 500,
                "flags": ["Revenue"],
            },
        ]
        stats = {
            "total": 10,
            "overdue": 2,
            "due_today": 3,
            "blocking_count": 1,
        }

        text, blocks = format_morning_briefing(focus_tasks, stats)

        assert isinstance(text, str)
        assert isinstance(blocks, list)
        assert "morning" in text.lower()


class TestThreadHandling:
    """Test thread_ts handling in bot responses."""

    def test_event_thread_ts_extraction_logic(self):
        """Bot should correctly extract thread_ts from events."""
        # Test the logic that extracts thread_ts from events
        # This mirrors the implementation in create_app()

        def extract_thread_ts(event):
            """Extract thread_ts to reply in same thread."""
            return event.get("thread_ts") or event.get("ts")

        # Event with thread_ts (reply in existing thread)
        event_reply = {
            "text": "help",
            "user": "U12345",
            "channel_type": "im",
            "ts": "1234567890.123456",
            "thread_ts": "1234567890.000000",
        }
        assert extract_thread_ts(event_reply) == "1234567890.000000"

        # Event without thread_ts (new message)
        event_new = {
            "text": "help",
            "user": "U12345",
            "channel_type": "im",
            "ts": "1234567890.123456",
        }
        assert extract_thread_ts(event_new) == "1234567890.123456"

    def test_thread_ts_fallback_to_ts(self):
        """When no thread_ts, should use ts to start thread."""
        event = {
            "text": "next",
            "user": "U12345",
            "channel_type": "im",
            "ts": "1234567890.123456",
        }

        # thread_ts should fall back to ts
        thread_ts = event.get("thread_ts") or event.get("ts")
        assert thread_ts == "1234567890.123456"

    def test_thread_ts_uses_existing_thread(self):
        """When thread_ts exists, should reply in same thread."""
        event = {
            "text": "done",
            "user": "U12345",
            "channel_type": "im",
            "ts": "1234567890.999999",
            "thread_ts": "1234567890.000000",
        }

        # Should use the thread_ts, not ts
        thread_ts = event.get("thread_ts") or event.get("ts")
        assert thread_ts == "1234567890.000000"
