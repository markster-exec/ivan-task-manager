"""Tests for Slack interactive component handlers."""

from backend.app.slack_actions import (
    TEAM_MEMBERS,
)
from backend.app.slack_blocks import (
    action_buttons,
    defer_modal,
    done_modal,
    snooze_modal,
    delegate_modal,
)


class TestTeamMembers:
    """Test team member mappings."""

    def test_attila_mapping(self):
        assert TEAM_MEMBERS["attila"]["clickup_id"] == "81842673"
        assert TEAM_MEMBERS["attila"]["github_username"] == "atiti"
        assert TEAM_MEMBERS["attila"]["display_name"] == "Attila"

    def test_tamas_mapping(self):
        assert TEAM_MEMBERS["tamas"]["clickup_id"] == "2695145"
        assert TEAM_MEMBERS["tamas"]["github_username"] is None
        assert TEAM_MEMBERS["tamas"]["display_name"] == "Tamas"


class TestActionButtons:
    """Test action button block creation."""

    def test_action_buttons_structure(self):
        buttons = action_buttons("task123")
        assert buttons["type"] == "actions"
        assert buttons["block_id"] == "task_actions_task123"
        assert len(buttons["elements"]) == 4

    def test_defer_button(self):
        buttons = action_buttons("task123")
        defer = buttons["elements"][0]
        assert defer["action_id"] == "defer_button"
        assert defer["value"] == "task123"
        assert defer["text"]["text"] == "Defer"

    def test_done_button(self):
        buttons = action_buttons("task123")
        done = buttons["elements"][1]
        assert done["action_id"] == "done_button"
        assert done["value"] == "task123"
        assert done["style"] == "primary"

    def test_snooze_button(self):
        buttons = action_buttons("task123")
        snooze = buttons["elements"][2]
        assert snooze["action_id"] == "snooze_button"
        assert snooze["value"] == "task123"

    def test_delegate_button(self):
        buttons = action_buttons("task123")
        delegate = buttons["elements"][3]
        assert delegate["action_id"] == "delegate_button"
        assert delegate["value"] == "task123"


class TestDeferModal:
    """Test defer modal structure."""

    def test_defer_modal_structure(self):
        modal = defer_modal("task123", "Test Task")
        assert modal["type"] == "modal"
        assert modal["callback_id"] == "defer_modal"
        assert modal["private_metadata"] == "task123"

    def test_defer_modal_has_options(self):
        modal = defer_modal("task123", "Test Task")
        select = modal["blocks"][1]["element"]
        options = select["options"]
        assert len(options) == 4
        # Check option values are days
        values = [o["value"] for o in options]
        assert "1" in values  # tomorrow
        assert "3" in values
        assert "7" in values
        assert "14" in values


class TestDoneModal:
    """Test done modal structure."""

    def test_done_modal_structure(self):
        modal = done_modal("task123", "Test Task")
        assert modal["type"] == "modal"
        assert modal["callback_id"] == "done_modal"
        assert modal["private_metadata"] == "task123"

    def test_done_modal_context_optional(self):
        modal = done_modal("task123", "Test Task")
        context_block = modal["blocks"][1]
        assert context_block["optional"] is True

    def test_done_modal_max_length(self):
        modal = done_modal("task123", "Test Task")
        text_input = modal["blocks"][1]["element"]
        assert text_input["max_length"] == 500


class TestSnoozeModal:
    """Test snooze modal structure."""

    def test_snooze_modal_structure(self):
        modal = snooze_modal("task123", "Test Task")
        assert modal["type"] == "modal"
        assert modal["callback_id"] == "snooze_modal"
        assert modal["private_metadata"] == "task123"

    def test_snooze_modal_has_options(self):
        modal = snooze_modal("task123", "Test Task")
        select = modal["blocks"][2]["element"]
        options = select["options"]
        values = [o["value"] for o in options]
        assert "1" in values  # 1 day
        assert "3" in values
        assert "7" in values


class TestDelegateModal:
    """Test delegate modal structure."""

    def test_delegate_modal_structure(self):
        modal = delegate_modal("task123", "Test Task")
        assert modal["type"] == "modal"
        assert modal["callback_id"] == "delegate_modal"
        assert modal["private_metadata"] == "task123"

    def test_delegate_modal_has_team_options(self):
        modal = delegate_modal("task123", "Test Task")
        select = modal["blocks"][1]["element"]
        options = select["options"]
        values = [o["value"] for o in options]
        assert "attila" in values
        assert "tamas" in values
