"""Slack notification system.

Handles:
- Instant notifications for urgent tasks (score >= 1000)
- Hourly digests for non-urgent updates
- Morning briefings at configured time
"""

import logging
import hashlib
from datetime import datetime, time
from typing import Optional, TYPE_CHECKING

from slack_sdk import WebClient

if TYPE_CHECKING:
    from .events import Event
from slack_sdk.errors import SlackApiError

from .config import get_settings
from .models import Task, NotificationLog, SessionLocal
from .scorer import get_score_breakdown, get_urgency_label
from .escalation import (
    calculate_escalation_level,
    group_tasks_by_escalation,
    should_consolidate,
    get_tasks_needing_notification,
)
from .slack_blocks import (
    format_escalation_message,
    format_grouped_escalation,
    format_briefing_with_buttons,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class SlackNotifier:
    """Send notifications via Slack."""

    def __init__(self):
        self.client = WebClient(token=settings.slack_bot_token)
        self.ivan_user_id = settings.slack_ivan_user_id

    def is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours."""
        now = datetime.now().time()
        start = time.fromisoformat(settings.quiet_hours_start)
        end = time.fromisoformat(settings.quiet_hours_end)

        # Handle overnight quiet hours (e.g., 22:00 - 07:00)
        if start > end:
            return now >= start or now <= end
        else:
            return start <= now <= end

    def _should_send(
        self, notification_type: str, task_id: Optional[str], message: str
    ) -> bool:
        """Check if notification should be sent (not duplicate, not quiet hours)."""
        if self.is_quiet_hours() and notification_type != "morning":
            logger.debug("Skipping notification during quiet hours")
            return False

        # Check for duplicate
        message_hash = hashlib.md5(
            f"{notification_type}:{task_id}:{message[:100]}".encode()
        ).hexdigest()
        db = SessionLocal()
        try:
            existing = (
                db.query(NotificationLog)
                .filter(NotificationLog.message_hash == message_hash)
                .first()
            )
            return existing is None
        finally:
            db.close()

    def _log_notification(
        self, notification_type: str, task_id: Optional[str], message: str
    ):
        """Log sent notification to avoid duplicates."""
        message_hash = hashlib.md5(
            f"{notification_type}:{task_id}:{message[:100]}".encode()
        ).hexdigest()
        db = SessionLocal()
        try:
            log = NotificationLog(
                notification_type=notification_type,
                task_id=task_id,
                message_hash=message_hash,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

    async def send_dm(
        self,
        message: str,
        notification_type: str = "instant",
        task_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
    ):
        """Send a direct message to Ivan.

        Args:
            message: The message to send
            notification_type: Type for deduplication (instant, morning, digest)
            task_id: Optional task ID for deduplication
            thread_ts: Optional thread timestamp to reply in a thread
        """
        if not self._should_send(notification_type, task_id, message):
            return False

        try:
            kwargs = {
                "channel": self.ivan_user_id,
                "text": message,
                "mrkdwn": True,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            self.client.chat_postMessage(**kwargs)
            self._log_notification(notification_type, task_id, message)
            logger.info(f"Sent {notification_type} notification")
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    async def send_instant_notification(self, task: Task, reason: str):
        """Send instant notification for urgent task."""
        breakdown = get_score_breakdown(task)

        message = f"""🚨 *Urgent Task Alert*

<{task.url}|*{task.title}*>
Score: {task.score} | {breakdown['urgency_label']}
Reason: {reason}"""

        await self.send_dm(message, "instant", task.id)

    async def send_morning_briefing(self, tasks: list[Task]):
        """Send morning briefing with top priorities."""
        if not tasks:
            message = "☀️ *Good morning, Ivan*\n\nNo tasks in queue. Enjoy your day!"
            await self.send_dm(message, "morning")
            return

        # Top 3 focus tasks
        top_tasks = tasks[:3]
        focus_lines = []
        for i, task in enumerate(top_tasks, 1):
            breakdown = get_score_breakdown(task)
            flags = []
            if task.is_revenue:
                flags.append("Revenue")
            if task.is_blocking:
                flags.append(f"Blocking: {', '.join(task.is_blocking)}")
            flags.append(breakdown["urgency_label"])

            focus_lines.append(
                f"{i}. <{task.url}|{task.title}> (Score: {task.score})\n"
                f"   → {' | '.join(flags)}"
            )

        # Summary stats
        overdue = sum(1 for t in tasks if get_urgency_label(t.due_date) == "Overdue")
        due_today = sum(
            1 for t in tasks if get_urgency_label(t.due_date) == "Due today"
        )
        blocking = set()
        for t in tasks:
            blocking.update(t.is_blocking or [])

        message = f"""☀️ *Good morning, Ivan*

🔥 *TOP 3 FOCUS*
{chr(10).join(focus_lines)}

📊 *SUMMARY*
• {overdue} tasks overdue
• {due_today} tasks due today
• {len(blocking)} people waiting on you ({', '.join(blocking) if blocking else 'none'})

Type `ivan next` to start working."""

        await self.send_dm(message, "morning")

    async def send_hourly_digest(
        self, new_tasks: list[Task], updated_tasks: list[Task]
    ):
        """Send hourly digest of non-urgent updates."""
        if not new_tasks and not updated_tasks:
            return

        lines = []

        if new_tasks:
            lines.append("*New tasks assigned:*")
            for task in new_tasks[:5]:
                lines.append(f"• <{task.url}|{task.title}>")

        if updated_tasks:
            lines.append("\n*Updates on your tasks:*")
            for task in updated_tasks[:5]:
                lines.append(f"• <{task.url}|{task.title}>")

        message = f"""📋 *Hourly Update*

{chr(10).join(lines)}

Type `ivan tasks` for full list."""

        await self.send_dm(message, "digest")

    async def notify_blocker(self, blocker_user: str, task: Task, reason: str):
        """Notify someone that Ivan is blocked on them."""
        user_ids = {
            "tamas": "U0853TD9VFF",
            "attila": "U0856NMSALA",
        }

        user_id = user_ids.get(blocker_user)
        if not user_id:
            logger.warning(f"Unknown user: {blocker_user}")
            return

        message = f"""👋 *Hey!*

Ivan is blocked on a task waiting for you:

<{task.url}|*{task.title}*>
Reason: {reason}"""

        try:
            self.client.chat_postMessage(
                channel=user_id,
                text=message,
                mrkdwn=True,
            )
            logger.info(f"Notified {blocker_user} about blocker")
        except SlackApiError as e:
            logger.error(f"Failed to notify {blocker_user}: {e}")

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
            return f"📢 *Notification*\n" f'"{task.title}"\n' f"<{task.url}|View task>"

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

    async def send_escalation_notification(self, task: Task) -> bool:
        """Send escalation notification for an overdue task.

        Only sends for tasks 3+ days overdue.
        Uses Block Kit with action buttons.

        Args:
            task: The overdue task

        Returns:
            True if notification was sent
        """
        level = calculate_escalation_level(task)
        if level < 3:
            logger.debug(f"Task {task.id} not at escalation level, skipping")
            return False

        due_str = task.due_date.isoformat() if task.due_date else "No date"
        text, blocks = format_escalation_message(
            title=task.title,
            url=task.url,
            due_date=due_str,
            escalation_level=level,
            task_id=task.id,
        )

        if not self._should_send("escalation", task.id, text):
            return False

        try:
            self.client.chat_postMessage(
                channel=self.ivan_user_id,
                text=text,
                blocks=blocks,
            )
            self._log_notification("escalation", task.id, text)

            # Update last notified
            db = SessionLocal()
            try:
                db_task = db.query(Task).filter(Task.id == task.id).first()
                if db_task:
                    from datetime import datetime

                    db_task.last_notified_at = datetime.utcnow()
                    db_task.escalation_level = level
                    db.commit()
            finally:
                db.close()

            logger.info(f"Sent escalation notification for {task.id} at level {level}")
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send escalation notification: {e}")
            return False

    async def send_grouped_escalation(
        self, tasks: list[Task], escalation_level: int
    ) -> bool:
        """Send a grouped notification for multiple tasks at same escalation level.

        Args:
            tasks: List of tasks to group
            escalation_level: Shared escalation level

        Returns:
            True if notification was sent
        """
        if len(tasks) < 3:
            # Not enough to consolidate, send individually
            for task in tasks:
                await self.send_escalation_notification(task)
            return True

        tasks_data = [
            {
                "title": t.title,
                "url": t.url,
                "due_date": t.due_date.isoformat() if t.due_date else "No date",
                "task_id": t.id,
            }
            for t in tasks
        ]

        text, blocks = format_grouped_escalation(tasks_data, escalation_level)

        # Use first task ID for deduplication
        task_ids = ",".join(t.id for t in tasks[:3])
        if not self._should_send("escalation_group", task_ids, text):
            return False

        try:
            self.client.chat_postMessage(
                channel=self.ivan_user_id,
                text=text,
                blocks=blocks,
            )
            self._log_notification("escalation_group", task_ids, text)
            logger.info(
                f"Sent grouped escalation for {len(tasks)} tasks at level {escalation_level}"
            )
            return True
        except SlackApiError as e:
            logger.error(f"Failed to send grouped escalation: {e}")
            return False

    async def send_escalation_notifications(self) -> int:
        """Process all tasks needing escalation notifications.

        Handles consolidation: 3+ tasks at same level → one grouped message.

        Returns:
            Number of notifications sent
        """
        db = SessionLocal()
        try:
            tasks = get_tasks_needing_notification(db)
            if not tasks:
                return 0

            grouped = group_tasks_by_escalation(tasks)
            sent_count = 0

            for level, level_tasks in grouped.items():
                if should_consolidate(level_tasks):
                    if await self.send_grouped_escalation(level_tasks, level):
                        sent_count += 1
                else:
                    for task in level_tasks:
                        if await self.send_escalation_notification(task):
                            sent_count += 1

            return sent_count
        finally:
            db.close()

    async def send_enhanced_morning_briefing(
        self, location: Optional[str] = None
    ) -> bool:
        """Send enhanced morning briefing with Block Kit formatting.

        Args:
            location: Optional current location string

        Returns:
            True if sent successfully
        """
        from .briefing import generate_morning_briefing

        db = SessionLocal()
        try:
            briefing = generate_morning_briefing(db, location=location)

            # Convert to format expected by slack_blocks
            top_tasks = [
                {
                    "title": t.title,
                    "url": t.url,
                    "score": t.score,
                    "flags": t.flags,
                    "task_id": t.id,
                }
                for t in briefing.top_tasks
            ]

            stats = {
                "total": briefing.stats.total,
                "overdue": briefing.stats.overdue,
                "due_today": briefing.stats.due_today,
                "blocking_people": briefing.stats.blocking_people,
            }

            calendar_events = [
                {"time": e.time, "title": e.title} for e in briefing.calendar_events
            ]

            text, blocks = format_briefing_with_buttons(
                greeting=briefing.greeting,
                location=briefing.location,
                top_tasks=top_tasks,
                stats=stats,
                calendar_events=calendar_events,
                suggestion=briefing.suggestion,
            )

            if not self._should_send("morning", None, text):
                return False

            self.client.chat_postMessage(
                channel=self.ivan_user_id,
                text=text,
                blocks=blocks,
            )
            self._log_notification("morning", None, text)
            logger.info("Sent enhanced morning briefing")
            return True

        except SlackApiError as e:
            logger.error(f"Failed to send morning briefing: {e}")
            return False
        finally:
            db.close()
