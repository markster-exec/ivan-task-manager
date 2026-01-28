"""Tests for event detector."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from app.events import EventType
from app.event_detector import EventDetector


@pytest.fixture
def detector():
    """Create EventDetector instance."""
    return EventDetector()


@pytest.fixture
def mock_task():
    """Create mock task."""
    task = MagicMock()
    task.id = "clickup:123"
    task.status = "todo"
    task.assignee = "ivan"
    task.due_date = None
    task.score = 600
    task.blocked_by = []
    # prev_assignee=ivan prevents assignment events in non-assignment tests
    task.notification_state = {"prev_assignee": "ivan"}
    return task


class TestDeadlineDetection:
    """Tests for deadline warning detection."""

    def test_deadline_24h_generates_event(self, detector, mock_task):
        """Task due in 24h should generate deadline_warning event."""
        mock_task.due_date = date.today() + timedelta(days=1)
        mock_task.notification_state = {"prev_assignee": "ivan"}  # No deadline notified

        events = detector.detect_from_sync(mock_task)

        deadline_events = [e for e in events if e.trigger == EventType.DEADLINE_WARNING]
        assert len(deadline_events) == 1
        assert deadline_events[0].fingerprint == "24h"

    def test_deadline_2h_generates_event(self, detector, mock_task):
        """Task due today should generate 2h warning."""
        mock_task.due_date = date.today()
        mock_task.notification_state = {"last_deadline_notified": "24h"}

        events = detector.detect_from_sync(mock_task)

        deadline_events = [e for e in events if e.trigger == EventType.DEADLINE_WARNING]
        assert len(deadline_events) == 1
        assert deadline_events[0].fingerprint == "2h"

    def test_deadline_already_notified_no_event(self, detector, mock_task):
        """Already notified deadline should not generate event."""
        mock_task.due_date = date.today() + timedelta(days=1)
        mock_task.notification_state = {"last_deadline_notified": "24h"}

        events = detector.detect_from_sync(mock_task)

        deadline_events = [e for e in events if e.trigger == EventType.DEADLINE_WARNING]
        assert len(deadline_events) == 0


class TestOverdueDetection:
    """Tests for overdue detection."""

    def test_overdue_task_generates_event(self, detector, mock_task):
        """Overdue task should generate overdue event."""
        mock_task.due_date = date.today() - timedelta(days=1)
        mock_task.notification_state = {}

        events = detector.detect_from_sync(mock_task)

        overdue_events = [e for e in events if e.trigger == EventType.OVERDUE]
        assert len(overdue_events) == 1

    def test_overdue_already_notified_today_no_event(self, detector, mock_task):
        """Overdue notified today should not generate event."""
        mock_task.due_date = date.today() - timedelta(days=1)
        mock_task.notification_state = {"last_overdue_notified": str(date.today())}

        events = detector.detect_from_sync(mock_task)

        overdue_events = [e for e in events if e.trigger == EventType.OVERDUE]
        assert len(overdue_events) == 0


class TestStatusChangeDetection:
    """Tests for status change detection."""

    def test_status_to_blocked_generates_event(self, detector, mock_task):
        """Status change to blocked should generate event."""
        mock_task.status = "blocked"
        mock_task.notification_state = {"prev_status": "todo"}

        events = detector.detect_from_sync(mock_task)

        status_events = [e for e in events if e.trigger == EventType.STATUS_CRITICAL]
        assert len(status_events) == 1
        assert "blocked" in status_events[0].fingerprint


class TestAssigneeChangeDetection:
    """Tests for assignee change detection."""

    def test_assigned_to_me_generates_event(self, detector, mock_task):
        """Being assigned a task should generate event."""
        mock_task.assignee = "ivan"
        mock_task.notification_state = {"prev_assignee": "tamas"}

        events = detector.detect_from_sync(mock_task)

        assigned_events = [e for e in events if e.trigger == EventType.ASSIGNED]
        assert len(assigned_events) == 1

    def test_already_assigned_no_event(self, detector, mock_task):
        """No change in assignee should not generate event."""
        mock_task.assignee = "ivan"
        mock_task.notification_state = {"prev_assignee": "ivan"}

        events = detector.detect_from_sync(mock_task)

        assigned_events = [e for e in events if e.trigger == EventType.ASSIGNED]
        assert len(assigned_events) == 0
