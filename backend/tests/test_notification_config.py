"""Tests for notification config loader."""

from app.notification_config import (
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

    def test_threshold_exact_match(self):
        """Task score exactly matching threshold should notify."""
        config = NotificationConfig()
        config.threshold = 500
        assert config.should_notify("assigned", task_score=500) is True


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
        config_path.write_text(
            """
mode: full
threshold: 0
triggers:
  deadline_warning: true
  comment_on_owned: true
"""
        )
        config = load_notification_config(config_path)
        assert config.mode == "full"
        assert config.threshold == 0
        assert config.triggers["comment_on_owned"] is True

    def test_invalid_trigger_name_ignored(self, tmp_path):
        """Invalid trigger names in config should be ignored."""
        config_path = tmp_path / "notifications.yaml"
        config_path.write_text(
            """
triggers:
  deadline_warning: true
  fake_trigger: true
"""
        )
        config = load_notification_config(config_path)
        assert "fake_trigger" not in config.triggers

    def test_malformed_yaml_returns_defaults(self, tmp_path):
        """Malformed YAML should return defaults and not crash."""
        config_path = tmp_path / "notifications.yaml"
        config_path.write_text("mode: [invalid yaml structure")
        config = load_notification_config(config_path)
        assert config.mode == "focus"  # Should get defaults
