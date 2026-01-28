"""Event data classes for notification system."""

from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """Types of events that can trigger notifications."""

    DEADLINE_WARNING = "deadline_warning"
    OVERDUE = "overdue"
    ASSIGNED = "assigned"
    STATUS_CRITICAL = "status_critical"
    MENTIONED = "mentioned"
    COMMENT_ON_OWNED = "comment_on_owned"
    BLOCKER_RESOLVED = "blocker_resolved"


@dataclass
class Event:
    """Represents a notification event.

    Attributes:
        trigger: The type of event (from EventType enum)
        task_id: The task this event relates to
        fingerprint: Unique identifier for this specific event instance
        context: Additional data for message formatting
    """

    trigger: EventType
    task_id: str
    fingerprint: str
    context: dict = field(default_factory=dict)

    @property
    def dedupe_key(self) -> str:
        """Generate deduplication key for this event."""
        return f"{self.trigger.value}:{self.task_id}:{self.fingerprint}"
