# Phase 4F: Event-driven Notifications Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace score-based notifications with event-driven triggers that only fire when something changes.

**Architecture:** Three new components: EventDetector (detects changes), NotificationFilter (applies config rules), and NotificationConfig (loads YAML). These integrate with existing SlackNotifier for delivery. Task model gets a `notification_state` JSON column for tracking.

**Tech Stack:** Python, SQLAlchemy, PyYAML, pytest

---

## Task 1: Add notification_state Column to Task Model

**Files:**
- Modify: `backend/app/models.py:25-52`
- Test: `backend/tests/test_models.py` (new file)

**Step 1: Write the failing test**

Create `backend/tests/test_models.py`:

```python
"""Tests for models."""

import pytest
from backend.app.models import Task


class TestTaskNotificationState:
    """Tests for Task.notification_state column."""

    def test_notification_state_defaults_to_empty_dict(self):
        """New task should have empty notification_state."""
        task = Task(
            id="test:1",
            source="test",
            title="Test Task",
            status="todo",
            url="http://example.com",
        )
        assert task.notification_state == {}

    def test_notification_state_can_store_dict(self):
        """notification_state should store and retrieve dict."""
        task = Task(
            id="test:2",
            source="test",
            title="Test Task",
            status="todo",
            url="http://example.com",
        )
        task.notification_state = {
            "prev_status": "todo",
            "prev_assignee": "ivan",
            "dedupe_keys": ["key1", "key2"],
        }
        assert task.notification_state["prev_status"] == "todo"
        assert task.notification_state["dedupe_keys"] == ["key1", "key2"]
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_models.py -v`
Expected: FAIL with "AttributeError: notification_state"

**Step 3: Add notification_state column to Task model**

In `backend/app/models.py`, add after line 52 (after `updated_at`):

```python
    # Notification tracking (event-driven notifications)
    notification_state = Column(JSON, default=dict)
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_models.py
git commit -m "feat(models): add notification_state JSON column to Task"
```

---

## Task 2: Create Notification Config Loader

**Files:**
- Create: `config/notifications.yaml`
- Create: `backend/app/notification_config.py`
- Test: `backend/tests/test_notification_config.py`

**Step 1: Create default config file**

Create `config/notifications.yaml`:

```yaml
# Notification Configuration
# Mode sets defaults when switched. Individual triggers override.

mode: focus  # focus | full | off

# Only notify if task.score >= this (0 = all)
# NOTE: deadline_warning and overdue ignore threshold (time-sensitive)
threshold: 500

triggers:
  deadline_warning: true   # ignores threshold
  overdue: true            # ignores threshold
  assigned: true
  status_critical: true
  mentioned: true
  comment_on_owned: false  # off by default (can be noisy)
  blocker_resolved: true

# Preset modes (for reference):
# focus: threshold=500, deadline_warning, overdue, mentioned, blocker_resolved ON
# full: threshold=0, all triggers ON
# off: all notifications disabled
```

**Step 2: Write failing tests**

Create `backend/tests/test_notification_config.py`:

```python
"""Tests for notification config loader."""

import pytest
from pathlib import Path
from backend.app.notification_config import (
    NotificationConfig,
    load_notification_config,
    THRESHOLD_EXEMPT_TRIGGERS,
)


class TestNotificationConfig:
    """Tests for NotificationConfig class."""

    def test_default_config_values(self):
        """Config should have sensible defaults."""
        config = NotificationConfig()
        assert config.mode == "focus"
        assert config.threshold == 500
        assert config.triggers["deadline_warning"] is True
        assert config.triggers["comment_on_owned"] is False

    def test_is_trigger_enabled(self):
        """is_trigger_enabled should check trigger status."""
        config = NotificationConfig()
        assert config.is_trigger_enabled("deadline_warning") is True
        assert config.is_trigger_enabled("comment_on_owned") is False
        assert config.is_trigger_enabled("unknown_trigger") is False

    def test_is_threshold_exempt(self):
        """deadline_warning and overdue should be threshold exempt."""
        assert "deadline_warning" in THRESHOLD_EXEMPT_TRIGGERS
        assert "overdue" in THRESHOLD_EXEMPT_TRIGGERS
        assert "assigned" not in THRESHOLD_EXEMPT_TRIGGERS

    def test_should_notify_respects_threshold(self):
        """should_notify should check threshold for non-exempt triggers."""
        config = NotificationConfig()
        config.threshold = 500

        # Below threshold, non-exempt trigger
        assert config.should_notify("assigned", task_score=400) is False
        # Above threshold, non-exempt trigger
        assert config.should_notify("assigned", task_score=600) is True
        # Below threshold, exempt trigger (deadline)
        assert config.should_notify("deadline_warning", task_score=100) is True

    def test_mode_off_disables_all(self):
        """Mode 'off' should disable all notifications."""
        config = NotificationConfig()
        config.mode = "off"
        assert config.should_notify("deadline_warning", task_score=1000) is False

    def test_trigger_disabled_returns_false(self):
        """Disabled trigger should not notify."""
        config = NotificationConfig()
        config.triggers["comment_on_owned"] = False
        assert config.should_notify("comment_on_owned", task_score=1000) is False


class TestLoadConfig:
    """Tests for config file loading."""

    def test_load_missing_file_returns_defaults(self, tmp_path):
        """Missing config file should return defaults."""
        config = load_notification_config(tmp_path / "missing.yaml")
        assert config.mode == "focus"
        assert config.threshold == 500

    def test_load_valid_config_file(self, tmp_path):
        """Valid config file should be loaded."""
        config_path = tmp_path / "notifications.yaml"
        config_path.write_text("""
mode: full
threshold: 0
triggers:
  deadline_warning: true
  comment_on_owned: true
""")
        config = load_notification_config(config_path)
        assert config.mode == "full"
        assert config.threshold == 0
        assert config.triggers["comment_on_owned"] is True
```

**Step 3: Run test to verify it fails**

Run: `pytest backend/tests/test_notification_config.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 4: Implement notification_config.py**

Create `backend/app/notification_config.py`:

```python
"""Notification configuration loader."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Triggers that ignore threshold (time-sensitive)
THRESHOLD_EXEMPT_TRIGGERS = {"deadline_warning", "overdue"}

# All valid trigger names
VALID_TRIGGERS = {
    "deadline_warning",
    "overdue",
    "assigned",
    "status_critical",
    "mentioned",
    "comment_on_owned",
    "blocker_resolved",
}

# Default trigger states
DEFAULT_TRIGGERS = {
    "deadline_warning": True,
    "overdue": True,
    "assigned": True,
    "status_critical": True,
    "mentioned": True,
    "comment_on_owned": False,  # Off by default (noisy)
    "blocker_resolved": True,
}


@dataclass
class NotificationConfig:
    """Notification configuration."""

    mode: str = "focus"  # focus | full | off
    threshold: int = 500
    triggers: dict = field(default_factory=lambda: DEFAULT_TRIGGERS.copy())

    def is_trigger_enabled(self, trigger: str) -> bool:
        """Check if a trigger is enabled."""
        return self.triggers.get(trigger, False)

    def should_notify(self, trigger: str, task_score: int) -> bool:
        """Check if notification should be sent for this trigger and score."""
        # Mode off disables everything
        if self.mode == "off":
            return False

        # Check if trigger is enabled
        if not self.is_trigger_enabled(trigger):
            return False

        # Check threshold (exempt triggers skip this)
        if trigger not in THRESHOLD_EXEMPT_TRIGGERS:
            if task_score < self.threshold:
                return False

        return True


def load_notification_config(config_path: Optional[Path] = None) -> NotificationConfig:
    """Load notification config from YAML file.

    Args:
        config_path: Path to config file. If None, uses default location.

    Returns:
        NotificationConfig with values from file or defaults.
    """
    if config_path is None:
        # Default location relative to project root
        config_path = Path(__file__).parent.parent.parent / "config" / "notifications.yaml"

    config = NotificationConfig()

    if not config_path.exists():
        logger.info(f"Config file not found at {config_path}, using defaults")
        return config

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}

        if "mode" in data:
            config.mode = data["mode"]
        if "threshold" in data:
            config.threshold = int(data["threshold"])
        if "triggers" in data:
            for trigger, enabled in data["triggers"].items():
                if trigger in VALID_TRIGGERS:
                    config.triggers[trigger] = bool(enabled)

        logger.info(f"Loaded notification config from {config_path}")
        return config

    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return NotificationConfig()


# Global config instance (loaded on import)
_config: Optional[NotificationConfig] = None


def get_notification_config() -> NotificationConfig:
    """Get the global notification config (lazy loaded)."""
    global _config
    if _config is None:
        _config = load_notification_config()
    return _config
```

**Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_notification_config.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add config/notifications.yaml backend/app/notification_config.py backend/tests/test_notification_config.py
git commit -m "feat(config): add notification config loader with YAML support"
```

---

## Task 3: Create Event Data Class

**Files:**
- Create: `backend/app/events.py`
- Test: `backend/tests/test_events.py`

**Step 1: Write failing tests**

Create `backend/tests/test_events.py`:

```python
"""Tests for event data classes."""

import pytest
from backend.app.events import Event, EventType


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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_events.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement events.py**

Create `backend/app/events.py`:

```python
"""Event data classes for notification system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


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
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_events.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/events.py backend/tests/test_events.py
git commit -m "feat(events): add Event dataclass and EventType enum"
```

---

## Task 4: Create EventDetector - Sync-based Detection

**Files:**
- Create: `backend/app/event_detector.py`
- Test: `backend/tests/test_event_detector.py`

**Step 1: Write failing tests for deadline detection**

Create `backend/tests/test_event_detector.py`:

```python
"""Tests for event detector."""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock

from backend.app.events import Event, EventType
from backend.app.event_detector import EventDetector


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
    task.notification_state = {}
    return task


class TestDeadlineDetection:
    """Tests for deadline warning detection."""

    def test_deadline_24h_generates_event(self, detector, mock_task):
        """Task due in 24h should generate deadline_warning event."""
        mock_task.due_date = date.today() + timedelta(days=1)
        mock_task.notification_state = {}

        events = detector.detect_from_sync(mock_task)

        assert len(events) == 1
        assert events[0].trigger == EventType.DEADLINE_WARNING
        assert events[0].fingerprint == "24h"

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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_event_detector.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement event_detector.py**

Create `backend/app/event_detector.py`:

```python
"""Event detector for notification system.

Detects events by comparing current task state to previous state
stored in notification_state.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from .events import Event, EventType
from .models import Task

logger = logging.getLogger(__name__)

# Status values considered critical
CRITICAL_STATUSES = {"blocked", "urgent", "critical"}


class EventDetector:
    """Detects notification events from task state changes."""

    def detect_from_sync(self, task: Task) -> list[Event]:
        """Detect events by comparing current state to notification_state.

        Args:
            task: Task to check for events

        Returns:
            List of events detected
        """
        events = []
        state = task.notification_state or {}

        # Deadline warnings
        deadline_event = self._check_deadline(task, state)
        if deadline_event:
            events.append(deadline_event)

        # Overdue
        overdue_event = self._check_overdue(task, state)
        if overdue_event:
            events.append(overdue_event)

        # Status change to critical
        status_event = self._check_status_critical(task, state)
        if status_event:
            events.append(status_event)

        # Assignee change
        assigned_event = self._check_assigned(task, state)
        if assigned_event:
            events.append(assigned_event)

        # Blocker resolved
        blocker_event = self._check_blocker_resolved(task, state)
        if blocker_event:
            events.append(blocker_event)

        return events

    def _check_deadline(self, task: Task, state: dict) -> Optional[Event]:
        """Check for deadline warning events."""
        if not task.due_date:
            return None

        today = date.today()
        due = task.due_date if isinstance(task.due_date, date) else task.due_date.date()
        days_until = (due - today).days

        last_notified = state.get("last_deadline_notified")

        # Due today and haven't sent 2h warning
        if days_until == 0 and last_notified != "2h":
            return Event(
                trigger=EventType.DEADLINE_WARNING,
                task_id=task.id,
                fingerprint="2h",
                context={"due_date": str(due), "urgency": "today"},
            )

        # Due tomorrow and haven't sent 24h warning
        if days_until == 1 and last_notified is None:
            return Event(
                trigger=EventType.DEADLINE_WARNING,
                task_id=task.id,
                fingerprint="24h",
                context={"due_date": str(due), "urgency": "tomorrow"},
            )

        return None

    def _check_overdue(self, task: Task, state: dict) -> Optional[Event]:
        """Check for overdue events."""
        if not task.due_date:
            return None

        today = date.today()
        due = task.due_date if isinstance(task.due_date, date) else task.due_date.date()

        if due >= today:
            return None  # Not overdue

        # Only notify once per day
        last_notified = state.get("last_overdue_notified")
        if last_notified == str(today):
            return None

        return Event(
            trigger=EventType.OVERDUE,
            task_id=task.id,
            fingerprint=f"overdue:{today}",
            context={"due_date": str(due), "days_overdue": (today - due).days},
        )

    def _check_status_critical(self, task: Task, state: dict) -> Optional[Event]:
        """Check for status change to critical."""
        prev_status = state.get("prev_status")
        current_status = task.status.lower() if task.status else ""

        # Only trigger if changed TO a critical status
        if current_status in CRITICAL_STATUSES and prev_status != current_status:
            return Event(
                trigger=EventType.STATUS_CRITICAL,
                task_id=task.id,
                fingerprint=f"status={current_status}",
                context={"new_status": current_status, "prev_status": prev_status},
            )

        return None

    def _check_assigned(self, task: Task, state: dict) -> Optional[Event]:
        """Check for assignment to user."""
        prev_assignee = state.get("prev_assignee")
        current_assignee = task.assignee

        # Only trigger if assigned TO ivan (not away from)
        if current_assignee == "ivan" and prev_assignee != "ivan":
            return Event(
                trigger=EventType.ASSIGNED,
                task_id=task.id,
                fingerprint=f"assignee={current_assignee}",
                context={"prev_assignee": prev_assignee},
            )

        return None

    def _check_blocker_resolved(self, task: Task, state: dict) -> Optional[Event]:
        """Check if a blocker was resolved.

        Note: This requires tracking blocked_by list changes.
        For MVP, we detect when blocked_by becomes empty.
        """
        prev_blocked_by = state.get("prev_blocked_by", [])
        current_blocked_by = task.blocked_by or []

        # Was blocked, now not blocked
        if prev_blocked_by and not current_blocked_by:
            return Event(
                trigger=EventType.BLOCKER_RESOLVED,
                task_id=task.id,
                fingerprint="unblocked",
                context={"resolved_blockers": prev_blocked_by},
            )

        return None

    def parse_webhook_event(
        self, source: str, event_type: str, payload: dict
    ) -> Optional[Event]:
        """Parse webhook payload into Event.

        Args:
            source: 'github' or 'clickup'
            event_type: The webhook event type
            payload: The webhook payload

        Returns:
            Event if this is a notification-worthy event, None otherwise
        """
        logger.info(f"Webhook received: source={source}, event={event_type}")

        if source == "github":
            return self._parse_github_webhook(event_type, payload)
        elif source == "clickup":
            return self._parse_clickup_webhook(event_type, payload)

        return None

    def _parse_github_webhook(self, event_type: str, payload: dict) -> Optional[Event]:
        """Parse GitHub webhook for notification events."""
        # Comment created - check for mentions
        if event_type == "issue_comment" and payload.get("action") == "created":
            comment = payload.get("comment", {})
            issue = payload.get("issue", {})
            task_id = f"github:{issue.get('number')}"
            commenter = comment.get("user", {}).get("login", "unknown")
            body = comment.get("body", "")

            # Check if ivan is mentioned
            if "@ivanivanka" in body or "ivan" in body.lower():
                return Event(
                    trigger=EventType.MENTIONED,
                    task_id=task_id,
                    fingerprint=f"comment_id={comment.get('id')}",
                    context={"commenter": commenter, "body_preview": body[:100]},
                )

            # Check if ivan owns this task (comment_on_owned)
            assignee = issue.get("assignee", {})
            if assignee and assignee.get("login") == "ivanivanka":
                return Event(
                    trigger=EventType.COMMENT_ON_OWNED,
                    task_id=task_id,
                    fingerprint=f"comment_id={comment.get('id')}",
                    context={"commenter": commenter, "body_preview": body[:100]},
                )

        return None

    def _parse_clickup_webhook(self, event_type: str, payload: dict) -> Optional[Event]:
        """Parse ClickUp webhook for notification events."""
        task_id_raw = payload.get("task_id") or payload.get("task", {}).get("id")
        if not task_id_raw:
            return None

        task_id = f"clickup:{task_id_raw}"

        # Comment posted
        if event_type == "taskCommentPosted":
            history = payload.get("history_items", [{}])
            if history:
                comment_data = history[0].get("comment", {})
                commenter = comment_data.get("user", {}).get("username", "unknown")
                text = comment_data.get("text_content", "")
                comment_id = comment_data.get("id", "unknown")

                # Check for ivan mention
                if "@ivan" in text.lower() or "ivan" in text.lower():
                    return Event(
                        trigger=EventType.MENTIONED,
                        task_id=task_id,
                        fingerprint=f"comment_id={comment_id}",
                        context={"commenter": commenter, "body_preview": text[:100]},
                    )

                # Otherwise it's a comment on owned task
                return Event(
                    trigger=EventType.COMMENT_ON_OWNED,
                    task_id=task_id,
                    fingerprint=f"comment_id={comment_id}",
                    context={"commenter": commenter, "body_preview": text[:100]},
                )

        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_event_detector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/event_detector.py backend/tests/test_event_detector.py
git commit -m "feat(detector): add EventDetector for sync and webhook events"
```

---

## Task 5: Create NotificationFilter

**Files:**
- Create: `backend/app/notification_filter.py`
- Test: `backend/tests/test_notification_filter.py`

**Step 1: Write failing tests**

Create `backend/tests/test_notification_filter.py`:

```python
"""Tests for notification filter."""

import pytest
from unittest.mock import MagicMock

from backend.app.events import Event, EventType
from backend.app.notification_filter import NotificationFilter
from backend.app.notification_config import NotificationConfig


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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_notification_filter.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement notification_filter.py**

Create `backend/app/notification_filter.py`:

```python
"""Notification filter - decides whether to send a notification."""

import logging
from typing import TYPE_CHECKING

from .events import Event
from .notification_config import NotificationConfig, THRESHOLD_EXEMPT_TRIGGERS

if TYPE_CHECKING:
    from .models import Task

logger = logging.getLogger(__name__)


class NotificationFilter:
    """Filters events based on configuration rules."""

    def __init__(self, config: NotificationConfig):
        self.config = config

    def should_notify(self, event: Event, task: "Task") -> bool:
        """Check if notification should be sent for this event.

        Args:
            event: The event to check
            task: The task associated with the event

        Returns:
            True if notification should be sent
        """
        trigger = event.trigger.value

        # Check mode
        if self.config.mode == "off":
            logger.debug(f"Blocked {trigger}: mode is off")
            return False

        # Check trigger enabled
        if not self.config.is_trigger_enabled(trigger):
            logger.debug(f"Blocked {trigger}: trigger disabled")
            return False

        # Check threshold (exempt for deadline/overdue)
        if trigger not in THRESHOLD_EXEMPT_TRIGGERS:
            if task.score < self.config.threshold:
                logger.debug(
                    f"Blocked {trigger}: score {task.score} < threshold {self.config.threshold}"
                )
                return False

        # Check dedupe
        state = task.notification_state or {}
        dedupe_keys = state.get("dedupe_keys", [])
        if event.dedupe_key in dedupe_keys:
            logger.debug(f"Blocked {trigger}: duplicate event {event.dedupe_key}")
            return False

        logger.info(f"Allowing notification: {trigger} for {task.id}")
        return True
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_notification_filter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/notification_filter.py backend/tests/test_notification_filter.py
git commit -m "feat(filter): add NotificationFilter with config, threshold, dedupe"
```

---

## Task 6: Update SlackNotifier with Event-based Messages

**Files:**
- Modify: `backend/app/notifier.py`
- Test: `backend/tests/test_notifier.py` (new)

**Step 1: Write failing tests**

Create `backend/tests/test_notifier.py`:

```python
"""Tests for notifier event message formatting."""

import pytest
from unittest.mock import MagicMock, patch

from backend.app.events import Event, EventType
from backend.app.notifier import SlackNotifier


@pytest.fixture
def notifier():
    """Create notifier with mocked Slack client."""
    with patch("backend.app.notifier.WebClient"):
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
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_notifier.py -v`
Expected: FAIL with "AttributeError: format_event_message"

**Step 3: Add format_event_message to SlackNotifier**

In `backend/app/notifier.py`, add after the existing methods (after line 234):

```python
    def format_event_message(self, event: "Event", task: "Task") -> str:
        """Format notification message for an event.

        Args:
            event: The event that triggered the notification
            task: The task associated with the event

        Returns:
            Formatted message string
        """
        from .events import EventType

        trigger = event.trigger
        ctx = event.context

        if trigger == EventType.DEADLINE_WARNING:
            urgency = ctx.get("urgency", "soon")
            if urgency == "today":
                time_str = "in 2 hours"
            else:
                time_str = "in 24 hours"
            return (
                f"⏰ *Deadline {time_str}*\n"
                f'"{task.title}"\n'
                f"Due: {ctx.get('due_date', 'Unknown')}\n"
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.OVERDUE:
            days = ctx.get("days_overdue", 1)
            days_str = f"{days} day{'s' if days > 1 else ''}"
            return (
                f"🔴 *Overdue*\n"
                f'"{task.title}"\n'
                f"Was due: {ctx.get('due_date', 'Unknown')} ({days_str} ago)\n"
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.ASSIGNED:
            prev = ctx.get("prev_assignee", "someone")
            return (
                f"📥 *Newly assigned to you*\n"
                f'"{task.title}"\n'
                f"Previously: {prev or 'unassigned'}\n"
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.STATUS_CRITICAL:
            status = ctx.get("new_status", "critical")
            return (
                f"🚨 *Status changed to {status}*\n"
                f'"{task.title}"\n'
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.MENTIONED:
            commenter = ctx.get("commenter", "Someone")
            preview = ctx.get("body_preview", "")
            return (
                f"💬 *You were mentioned*\n"
                f'"{task.title}"\n'
                f"By: {commenter}\n"
                f'"{preview}"\n'
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.COMMENT_ON_OWNED:
            commenter = ctx.get("commenter", "Someone")
            return (
                f"💬 *New comment on your task*\n"
                f'"{task.title}"\n'
                f"By: {commenter}\n"
                f"<{task.url}|View task>"
            )

        elif trigger == EventType.BLOCKER_RESOLVED:
            return (
                f"✅ *Blocker resolved*\n"
                f'"{task.title}"\n'
                f"You can now proceed\n"
                f"<{task.url}|View task>"
            )

        else:
            return (
                f"📢 *Notification*\n"
                f'"{task.title}"\n'
                f"<{task.url}|View task>"
            )

    async def send_event_notification(self, event: "Event", task: "Task") -> bool:
        """Send notification for an event.

        Args:
            event: The event that triggered the notification
            task: The task associated with the event

        Returns:
            True if notification was sent successfully
        """
        message = self.format_event_message(event, task)
        return await self.send_dm(
            message,
            notification_type=event.trigger.value,
            task_id=task.id,
        )
```

Also add import at top of file:

```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .events import Event
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_notifier.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/notifier.py backend/tests/test_notifier.py
git commit -m "feat(notifier): add event-based message formatting"
```

---

## Task 7: Integrate Event System into main.py

**Files:**
- Modify: `backend/app/main.py`
- Update tests in: `backend/tests/test_api.py`

**Step 1: Update scheduled_sync to use event detection**

In `backend/app/main.py`, replace the `scheduled_sync` function (lines 97-115) with:

```python
async def scheduled_sync():
    """Scheduled sync job with event-based notifications."""
    from .event_detector import EventDetector
    from .notification_filter import NotificationFilter
    from .notification_config import get_notification_config

    logger.info("Running scheduled sync...")
    results = await sync_all_sources()
    logger.info(f"Sync complete: {results}")

    # Event-based notifications
    config = get_notification_config()
    detector = EventDetector()
    filter = NotificationFilter(config)

    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        for task in tasks:
            # Detect events from state changes
            events = detector.detect_from_sync(task)

            for event in events:
                # Check if we should notify
                if filter.should_notify(event, task):
                    # Send notification
                    success = await notifier.send_event_notification(event, task)

                    if success:
                        # Update notification state
                        state = task.notification_state or {}

                        # Add dedupe key
                        dedupe_keys = state.get("dedupe_keys", [])
                        dedupe_keys.append(event.dedupe_key)
                        # Keep only last 50 keys
                        state["dedupe_keys"] = dedupe_keys[-50:]

                        # Update trigger-specific state
                        if event.trigger.value == "deadline_warning":
                            state["last_deadline_notified"] = event.fingerprint
                        elif event.trigger.value == "overdue":
                            state["last_overdue_notified"] = str(date.today())

                        task.notification_state = state

            # Always update prev_* state for next comparison
            state = task.notification_state or {}
            state["prev_status"] = task.status
            state["prev_assignee"] = task.assignee
            state["prev_blocked_by"] = task.blocked_by or []
            task.notification_state = state

        db.commit()
    finally:
        db.close()
```

Add import at top:

```python
from datetime import date
```

**Step 2: Update webhook handlers to use event detection**

In `backend/app/main.py`, update the `github_webhook` function to add event detection after status updates. Add before the `return` statement:

```python
    # Event detection for comment notifications
    if event == "issue_comment" and action == "created":
        from .event_detector import EventDetector
        from .notification_filter import NotificationFilter
        from .notification_config import get_notification_config

        config = get_notification_config()
        detector = EventDetector()
        filter = NotificationFilter(config)

        evt = detector.parse_webhook_event("github", event, payload)
        if evt:
            task = db.query(Task).filter(Task.id == f"github:{payload.get('issue', {}).get('number')}").first()
            if task and filter.should_notify(evt, task):
                await notifier.send_event_notification(evt, task)
                # Update dedupe
                state = task.notification_state or {}
                dedupe_keys = state.get("dedupe_keys", [])
                dedupe_keys.append(evt.dedupe_key)
                state["dedupe_keys"] = dedupe_keys[-50:]
                task.notification_state = state
                db.commit()
```

Similarly update `clickup_webhook` to add:

```python
    # Event detection for comment notifications
    if event == "taskCommentPosted":
        from .event_detector import EventDetector
        from .notification_filter import NotificationFilter
        from .notification_config import get_notification_config

        config = get_notification_config()
        detector = EventDetector()
        filter = NotificationFilter(config)

        evt = detector.parse_webhook_event("clickup", event, payload)
        if evt and task:
            if filter.should_notify(evt, task):
                await notifier.send_event_notification(evt, task)
                # Update dedupe
                state = task.notification_state or {}
                dedupe_keys = state.get("dedupe_keys", [])
                dedupe_keys.append(evt.dedupe_key)
                state["dedupe_keys"] = dedupe_keys[-50:]
                task.notification_state = state
                db.commit()
```

**Step 3: Run all tests**

Run: `pytest backend/tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(main): integrate event-based notifications in sync and webhooks"
```

---

## Task 8: Update State After Notification

**Files:**
- Create helper in: `backend/app/notification_state.py`
- Test: `backend/tests/test_notification_state.py`

**Step 1: Write failing tests**

Create `backend/tests/test_notification_state.py`:

```python
"""Tests for notification state management."""

import pytest
from datetime import date
from unittest.mock import MagicMock

from backend.app.events import Event, EventType
from backend.app.notification_state import update_notification_state


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

        assert "assigned:clickup:123:assignee=ivan" in mock_task.notification_state["dedupe_keys"]

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

        assert mock_task.notification_state["last_overdue_notified"] == str(date.today())

    def test_limits_dedupe_keys_to_50(self, mock_task):
        """Should keep only last 50 dedupe keys."""
        mock_task.notification_state = {
            "dedupe_keys": [f"key{i}" for i in range(60)]
        }
        event = Event(
            trigger=EventType.ASSIGNED,
            task_id="clickup:123",
            fingerprint="new",
        )
        update_notification_state(mock_task, event)

        assert len(mock_task.notification_state["dedupe_keys"]) == 50
```

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_notification_state.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement notification_state.py**

Create `backend/app/notification_state.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_notification_state.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/notification_state.py backend/tests/test_notification_state.py
git commit -m "feat(state): add notification state management helpers"
```

---

## Task 9: Run Full Test Suite and Fix Integration

**Step 1: Run all tests**

Run: `pytest backend/tests/ -v`

**Step 2: Fix any failures**

Address any integration issues that arise.

**Step 3: Verify the app starts**

Run: `cd backend && python -c "from app.main import app; print('App loads OK')"`

**Step 4: Final commit**

```bash
git add -A
git commit -m "test: ensure all tests pass for Phase 4F"
```

---

## Task 10: Update Documentation

**Files:**
- Update: `STATE.md`
- Update: `CHANGELOG.md` (if exists)

**Step 1: Update STATE.md**

Update the STATE.md file to reflect Phase 4F completion.

**Step 2: Close GitHub Issue**

Run: `gh issue close 7 --repo markster-exec/ivan-task-manager --comment "Phase 4F complete. Event-driven notifications implemented."`

**Step 3: Push changes**

Run: `git push origin main`

**Step 4: Final commit**

```bash
git add STATE.md
git commit -m "docs: update STATE.md for Phase 4F completion"
```

---

## Success Criteria Checklist

After completing all tasks, verify:

- [ ] No notification unless something CHANGED
- [ ] Notification includes WHY it was sent (the trigger)
- [ ] User can configure which triggers they want (config/notifications.yaml)
- [ ] User can set threshold to filter low-priority events
- [ ] User can switch modes (focus/full/off)
- [ ] Deadline/overdue notifications fire regardless of threshold
- [ ] Same event via webhook + sync = single notification (dedupe works)
- [ ] Webhook arrivals logged for reliability monitoring
- [ ] All 100+ tests pass
- [ ] CI passes on GitHub
