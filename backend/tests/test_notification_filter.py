"""Tests for notification filter."""

import pytest
from unittest.mock import MagicMock

from app.events import Event, EventType
from app.notification_filter import NotificationFilter
from app.notification_config import NotificationConfig


@pytest.fixture
def config():
    """Create test config."""
    return NotificationConfig()


@pytest.fixture
def filter(config):
    """Create NotificationFilter instance."""
    return NotificationFilter(config)


@pytest.fixture
def mock_task():
    """Create mock task."""
    task = MagicMock()
    task.id = "clickup:123"
    task.score = 600
    task.notification_state = {"dedupe_keys": []}
    return task


class TestNotificationFilter:
    """Tests for NotificationFilter."""

    def test_passes_enabled_trigger_above_threshold(self, filter, mock_task):
        """Enabled trigger above threshold should pass."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="assignee=ivan",
        )
        assert filter.should_notify(event, mock_task) is True

    def test_blocks_disabled_trigger(self, filter, mock_task):
        """Disabled trigger should be blocked."""
        filter.config.triggers["comment_on_owned"] = False
        event = Event(
            trigger=EventType.COMMENT_ON_OWNED,
            task_id="clickup:123",
            fingerprint="comment_id=1",
        )
        assert filter.should_notify(event, mock_task) is False

    def test_blocks_below_threshold(self, filter, mock_task):
        """Below threshold should be blocked for non-exempt triggers."""
        mock_task.score = 100
        filter.config.threshold = 500
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="assignee=ivan",
        )
        assert filter.should_notify(event, mock_task) is False

    def test_passes_deadline_below_threshold(self, filter, mock_task):
        """Deadline warning should pass even below threshold."""
        mock_task.score = 100
        filter.config.threshold = 500
        event = Event(
            trigger=EventType.DEADLINE_WARNING,
            task_id="clickup:123",
            fingerprint="24h",
        )
        assert filter.should_notify(event, mock_task) is True

    def test_blocks_duplicate_event(self, filter, mock_task):
        """Already-sent event should be blocked."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="assignee=ivan",
        )
        mock_task.notification_state = {
            "dedupe_keys": ["assigned:clickup:123:assignee=ivan"]
        }
        assert filter.should_notify(event, mock_task) is False

    def test_mode_off_blocks_all(self, filter, mock_task):
        """Mode off should block all events."""
        filter.config.mode = "off"
        event = Event(
            trigger=EventType.DEADLINE_WARNING,
            task_id="clickup:123",
            fingerprint="24h",
        )
        assert filter.should_notify(event, mock_task) is False
