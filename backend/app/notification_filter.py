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
