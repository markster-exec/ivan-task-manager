"""Slack notification system.

Handles:
- Instant notifications for urgent tasks (score >= 1000)
- Hourly digests for non-urgent updates
- Morning briefings at configured time
"""

import logging
import hashlib
from datetime import datetime, time
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .config import get_settings
from .models import Task, NotificationLog, SessionLocal
from .scorer import get_score_breakdown, get_urgency_label

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

    def _should_send(self, notification_type: str, task_id: Optional[str], message: str) -> bool:
        """Check if notification should be sent (not duplicate, not quiet hours)."""
        if self.is_quiet_hours() and notification_type != "morning":
            logger.debug("Skipping notification during quiet hours")
            return False

        # Check for duplicate
        message_hash = hashlib.md5(f"{notification_type}:{task_id}:{message[:100]}".encode()).hexdigest()
        db = SessionLocal()
        try:
            existing = db.query(NotificationLog).filter(
                NotificationLog.message_hash == message_hash
            ).first()
            return existing is None
        finally:
            db.close()

    def _log_notification(self, notification_type: str, task_id: Optional[str], message: str):
        """Log sent notification to avoid duplicates."""
        message_hash = hashlib.md5(f"{notification_type}:{task_id}:{message[:100]}".encode()).hexdigest()
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

    async def send_dm(self, message: str, notification_type: str = "instant", task_id: Optional[str] = None):
        """Send a direct message to Ivan."""
        if not self._should_send(notification_type, task_id, message):
            return False

        try:
            response = self.client.chat_postMessage(
                channel=self.ivan_user_id,
                text=message,
                mrkdwn=True,
            )
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

*{task.title}*
Score: {task.score} | {breakdown['urgency_label']}
Reason: {reason}

🔗 {task.url}"""

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
                f"{i}. *{task.title}* (Score: {task.score})\n"
                f"   → {' | '.join(flags)}\n"
                f"   🔗 {task.url}"
            )

        # Summary stats
        overdue = sum(1 for t in tasks if get_urgency_label(t.due_date) == "Overdue")
        due_today = sum(1 for t in tasks if get_urgency_label(t.due_date) == "Due today")
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

    async def send_hourly_digest(self, new_tasks: list[Task], updated_tasks: list[Task]):
        """Send hourly digest of non-urgent updates."""
        if not new_tasks and not updated_tasks:
            return

        lines = []

        if new_tasks:
            lines.append("*New tasks assigned:*")
            for task in new_tasks[:5]:
                lines.append(f"• {task.title}")

        if updated_tasks:
            lines.append("\n*Updates on your tasks:*")
            for task in updated_tasks[:5]:
                lines.append(f"• {task.title}")

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

*{task.title}*
Reason: {reason}

🔗 {task.url}"""

        try:
            self.client.chat_postMessage(
                channel=user_id,
                text=message,
                mrkdwn=True,
            )
            logger.info(f"Notified {blocker_user} about blocker")
        except SlackApiError as e:
            logger.error(f"Failed to notify {blocker_user}: {e}")
