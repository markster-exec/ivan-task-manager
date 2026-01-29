"""Tests for models."""

from app.models import Task


class TestTaskActionField:
    """Tests for Task.action and linked_task_id columns."""

    def test_task_action_field(self, db_session):
        """Task should support action JSON field."""
        task = Task(
            id="proc-31-abc",
            source="processor",
            title="Respond to #31",
            status="pending",
            url="https://github.com/markster-exec/project-tracker/issues/31",
            action={
                "type": "github_comment",
                "issue": 31,
                "repo": "markster-exec/project-tracker",
                "body": "Keep it open.",
            },
            linked_task_id="github:31",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        assert task.action["type"] == "github_comment"
        assert task.action["body"] == "Keep it open."
        assert task.linked_task_id == "github:31"


class TestTaskNotificationState:
    """Tests for Task.notification_state column."""

    def test_notification_state_defaults_to_empty_dict(self, db_session):
        """New task should have empty notification_state after persistence."""
        task = Task(
            id="test:1",
            source="test",
            title="Test Task",
            status="todo",
            url="http://example.com",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        assert task.notification_state == {}

    def test_notification_state_can_store_dict(self, db_session):
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
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)
        assert task.notification_state["prev_status"] == "todo"
        assert task.notification_state["dedupe_keys"] == ["key1", "key2"]
