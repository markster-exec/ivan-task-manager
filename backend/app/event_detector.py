"""Event detector for notification system.

Detects events by comparing current task state to previous state
stored in notification_state.
"""

import logging
from datetime import date
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
