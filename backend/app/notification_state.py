"""Notification state management."""

from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .events import Event
    from .models import Task


def update_notification_state(task: "Task", event: "Event") -> None:
    """Update task notification state after sending notification.

    Args:
        task: The task to update
        event: The event that was notified
    """
    from .events import EventType

    state = task.notification_state or {}

    # Add dedupe key
    dedupe_keys = state.get("dedupe_keys", [])
    dedupe_keys.append(event.dedupe_key)
    # Keep only last 50 keys
    state["dedupe_keys"] = dedupe_keys[-50:]

    # Update trigger-specific state
    if event.trigger == EventType.DEADLINE_WARNING:
        state["last_deadline_notified"] = event.fingerprint
    elif event.trigger == EventType.OVERDUE:
        state["last_overdue_notified"] = str(date.today())

    # Update prev_* fields for next comparison
    state["prev_status"] = task.status
    state["prev_assignee"] = task.assignee
    state["prev_blocked_by"] = task.blocked_by or []

    task.notification_state = state


def update_prev_state_only(task: "Task") -> None:
    """Update only the prev_* fields without adding dedupe key.

    Use this for tasks that didn't generate notifications but need
    state tracking for future comparisons.

    Args:
        task: The task to update
    """
    state = task.notification_state or {}
    state["prev_status"] = task.status
    state["prev_assignee"] = task.assignee
    state["prev_blocked_by"] = task.blocked_by or []
    task.notification_state = state
