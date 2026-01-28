"""Tests for notification state management."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from app.events import Event, EventType
from app.notification_state import update_notification_state, update_prev_state_only


@pytest.fixture
def mock_task():
    """Create mock task."""
    task = MagicMock()
    task.id = "clickup:123"
    task.status = "in_progress"
    task.assignee = "ivan"
    task.blocked_by = []
    task.notification_state = {}
    return task


class TestUpdateNotificationState:
    """Tests for update_notification_state."""

    def test_adds_dedupe_key(self, mock_task):
        """Should add event dedupe key to state."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="assignee=ivan",
        )
        update_notification_state(mock_task, event)

        assert (
            "assigned:clickup:123:assignee=ivan"
            in mock_task.notification_state["dedupe_keys"]
        )

    def test_updates_prev_fields(self, mock_task):
        """Should update prev_status, prev_assignee, prev_blocked_by."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="assignee=ivan",
        )
        update_notification_state(mock_task, event)

        assert mock_task.notification_state["prev_status"] == "in_progress"
        assert mock_task.notification_state["prev_assignee"] == "ivan"
        assert mock_task.notification_state["prev_blocked_by"] == []

    def test_updates_deadline_notified(self, mock_task):
        """Deadline event should update last_deadline_notified."""
        event = Event(
            trigger=EventType.DEADLINE_WARNING,
            task_id="clickup:123",
            fingerprint="24h",
        )
        update_notification_state(mock_task, event)

        assert mock_task.notification_state["last_deadline_notified"] == "24h"

    def test_updates_overdue_notified(self, mock_task):
        """Overdue event should update last_overdue_notified."""
        event = Event(
            trigger=EventType.OVERDUE,
            task_id="clickup:123",
            fingerprint=f"overdue:{date.today()}",
        )
        update_notification_state(mock_task, event)

        assert mock_task.notification_state["last_overdue_notified"] == str(
            date.today()
        )

    def test_limits_dedupe_keys_to_50(self, mock_task):
        """Should keep only last 50 dedupe keys."""
        mock_task.notification_state = {"dedupe_keys": [f"key{i}" for i in range(60)]}
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="new",
        )
        update_notification_state(mock_task, event)

        assert len(mock_task.notification_state["dedupe_keys"]) == 50


class TestUpdatePrevStateOnly:
    """Tests for update_prev_state_only."""

    def test_updates_prev_fields_without_dedupe(self, mock_task):
        """Should update prev_* fields without adding dedupe key."""
        update_prev_state_only(mock_task)

        assert mock_task.notification_state["prev_status"] == "in_progress"
        assert mock_task.notification_state["prev_assignee"] == "ivan"
        assert mock_task.notification_state["prev_blocked_by"] == []
        assert "dedupe_keys" not in mock_task.notification_state

    def test_preserves_existing_dedupe_keys(self, mock_task):
        """Should preserve existing dedupe keys."""
        mock_task.notification_state = {"dedupe_keys": ["key1", "key2"]}
        update_prev_state_only(mock_task)

        assert mock_task.notification_state["dedupe_keys"] == ["key1", "key2"]
        assert mock_task.notification_state["prev_status"] == "in_progress"
