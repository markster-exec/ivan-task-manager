"""Tests for event data classes."""

from app.events import Event, EventType


class TestEvent:
    """Tests for Event class."""

    def test_event_creation(self):
        """Event should store trigger, task_id, and context."""
        event = Event(
            trigger=EventType.DEADLINE_WARNING,
            task_id="clickup:123",
            fingerprint="24h",
            context={"due_date": "2026-01-29"},
        )
        assert event.trigger == EventType.DEADLINE_WARNING
        assert event.task_id == "clickup:123"
        assert event.fingerprint == "24h"
        assert event.context["due_date"] == "2026-01-29"

    def test_dedupe_key_format(self):
        """dedupe_key should be {trigger}:{task_id}:{fingerprint}."""
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="github:45",
            fingerprint="assignee=ivan",
        )
        assert event.dedupe_key == "assigned:github:45:assignee=ivan"

    def test_event_type_values(self):
        """EventType enum should have correct string values."""
        assert EventType.DEADLINE_WARNING.value == "deadline_warning"
        assert EventType.OVERDUE.value == "overdue"
        assert EventType.ASSIGNED.value == "assigned"
        assert EventType.STATUS_CRITICAL.value == "status_critical"
        assert EventType.MENTIONED.value == "mentioned"
        assert EventType.COMMENT_ON_OWNED.value == "comment_on_owned"
        assert EventType.BLOCKER_RESOLVED.value == "blocker_resolved"
