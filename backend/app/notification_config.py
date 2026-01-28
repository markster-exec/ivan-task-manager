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
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "notifications.yaml"
        )

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
