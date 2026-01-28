"""Tests for notifier event message formatting."""

import pytest
from unittest.mock import MagicMock, patch

from app.events import Event, EventType
from app.notifier import SlackNotifier


@pytest.fixture
def notifier():
    """Create notifier with mocked Slack client."""
    with patch("app.notifier.WebClient"):
        n = SlackNotifier()
        n.client = MagicMock()
        return n


@pytest.fixture
def mock_task():
    """Create mock task."""
    task = MagicMock()
    task.id = "clickup:123"
    task.title = "Write proposal for Kyle"
    task.url = "https://app.clickup.com/t/123"
    task.due_date = None
    return task


class TestEventMessageFormatting:
    """Tests for event-specific message formatting."""

    def test_deadline_warning_message(self, notifier, mock_task):
        """Deadline warning should format correctly."""
        event = Event(
            trigger=EventType.DEADLINE_WARNING,
            task_id=mock_task.id,
            fingerprint="24h",
            context={"due_date": "2026-01-29", "urgency": "tomorrow"},
        )
        message = notifier.format_event_message(event, mock_task)

        assert "⏰" in message
        assert "Deadline" in message
        assert mock_task.title in message
        assert "View task" in message

    def test_overdue_message(self, notifier, mock_task):
        """Overdue should format correctly."""
        event = Event(
            trigger=EventType.OVERDUE,
            task_id=mock_task.id,
            fingerprint="overdue:2026-01-28",
            context={"due_date": "2026-01-27", "days_overdue": 1},
        )
        message = notifier.format_event_message(event, mock_task)

        assert "🔴" in message
        assert "Overdue" in message
        assert mock_task.title in message

    def test_assigned_message(self, notifier, mock_task):
        """Assigned should format correctly."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id=mock_task.id,
            fingerprint="assignee=ivan",
            context={"prev_assignee": "tamas"},
        )
        message = notifier.format_event_message(event, mock_task)

        assert "📥" in message
        assert "assigned" in message.lower()
        assert mock_task.title in message

    def test_mentioned_message(self, notifier, mock_task):
        """Mentioned should format correctly."""
        event = Event(
            trigger=EventType.MENTIONED,
            task_id=mock_task.id,
            fingerprint="comment_id=456",
            context={"commenter": "attila", "body_preview": "Hey @ivan check this"},
        )
        message = notifier.format_event_message(event, mock_task)

        assert "💬" in message
        assert "mentioned" in message.lower()
        assert "attila" in message.lower()

    def test_blocker_resolved_message(self, notifier, mock_task):
        """Blocker resolved should format correctly."""
        event = Event(
            trigger=EventType.BLOCKER_RESOLVED,
            task_id=mock_task.id,
            fingerprint="unblocked",
            context={"resolved_blockers": ["clickup:999"]},
        )
        message = notifier.format_event_message(event, mock_task)

        assert "✅" in message
        assert "resolved" in message.lower() or "unblocked" in message.lower()
