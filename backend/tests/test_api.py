"""Tests for API endpoints."""

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Task, CurrentTask
from app.writers.base import WriteResult


# Create test database with thread safety for TestClient
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    """Get test database session."""
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    # Import endpoint functions - they use Depends(get_db) which we override
    from app.main import (
        health_check,
        get_tasks,
        get_next_task,
        mark_done,
        skip_task,
        force_sync,
        get_morning_briefing,
        list_entities,
        get_entity_detail,
        reload_entities,
        complete_task_in_source,
        add_comment_to_source,
        create_task_in_source,
        github_webhook,
        clickup_webhook,
        get_db,
    )

    test_app = FastAPI()

    # Add routes manually without lifespan to avoid scheduler issues
    test_app.get("/health")(health_check)
    test_app.get("/tasks")(get_tasks)
    test_app.get("/next")(get_next_task)
    test_app.post("/done")(mark_done)
    test_app.post("/skip")(skip_task)
    test_app.post("/sync")(force_sync)
    test_app.get("/morning")(get_morning_briefing)
    test_app.get("/entities")(list_entities)
    test_app.get("/entities/{entity_id}")(get_entity_detail)
    test_app.post("/entities/reload")(reload_entities)
    test_app.post("/tasks/{task_id}/complete")(complete_task_in_source)
    test_app.post("/tasks/{task_id}/comment")(add_comment_to_source)
    test_app.post("/tasks")(create_task_in_source)
    test_app.post("/webhooks/github")(github_webhook)
    test_app.post("/webhooks/clickup")(clickup_webhook)

    # Override the database dependency
    test_app.dependency_overrides[get_db] = get_test_db

    with TestClient(test_app) as c:
        yield c


class TestHealthCheck:
    """Test health endpoint."""

    def test_health_returns_200(self, client):
        """Health check returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status(self, client):
        """Health check returns healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestGetTasks:
    """Test /tasks endpoint."""

    def test_empty_task_list(self, client):
        """Empty database returns empty list."""
        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_tasks_sorted(self, client):
        """Tasks are returned sorted by score."""
        # Add a task to the test database
        db = TestSessionLocal()
        task = Task(
            id="test:1",
            source="clickup",
            title="Task 1",
            description="Desc",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestNextTask:
    """Test /next endpoint."""

    def test_no_tasks(self, client):
        """No tasks returns appropriate message."""
        response = client.get("/next")
        assert response.status_code == 200
        data = response.json()
        assert data["task"] is None
        assert "No tasks" in data["message"]


class TestDoneEndpoint:
    """Test /done endpoint."""

    def test_no_current_task(self, client):
        """No current task returns error."""
        response = client.post("/done")
        assert response.status_code == 400

    def test_done_calls_writer_and_returns_completed_id(self, client):
        """Done endpoint calls writer and returns completed_task_id."""
        # Add a task and set it as current
        db = TestSessionLocal()
        task = Task(
            id="clickup:task123",
            source="clickup",
            title="Current Task",
            status="todo",
            assignee="ivan",
            url="http://clickup.com/task123",
            is_revenue=False,
            is_blocking_json=[],
        )
        current = CurrentTask(user_id="ivan", task_id="clickup:task123")
        db.add(task)
        db.add(current)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.complete.return_value = WriteResult(
                success=True, message="Task completed"
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/done")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["completed_task_id"] == "clickup:task123"
            assert "Completed" in data["message"]

            # Verify writer was called with correct source_id
            mock_writer.complete.assert_called_once_with("task123")


class TestSkipEndpoint:
    """Test /skip endpoint."""

    def test_no_current_task(self, client):
        """No current task returns error."""
        response = client.post("/skip")
        assert response.status_code == 400


class TestSyncEndpoint:
    """Test /sync endpoint."""

    def test_sync_returns_success(self, client):
        """Sync endpoint returns success structure."""
        with patch("app.main.sync_all_sources") as mock_sync:
            mock_sync.return_value = {"clickup": 5, "github": 3, "errors": []}

            response = client.post("/sync")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "results" in data


class TestMorningBriefing:
    """Test /morning endpoint."""

    def test_morning_returns_structure(self, client):
        """Morning briefing returns expected structure."""
        response = client.get("/morning")
        assert response.status_code == 200
        data = response.json()
        assert "top_tasks" in data
        assert "summary" in data


class TestEntityEndpoints:
    """Test /entities endpoints."""

    def test_get_entities(self, client, temp_entities_dir):
        """Test listing all entities."""
        from app import entity_loader

        entity_loader.load_entities(temp_entities_dir)

        response = client.get("/entities")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["name"] == "Mark Smith"

    def test_get_entity_by_id(self, client, temp_entities_dir):
        """Test getting specific entity."""
        from app import entity_loader

        entity_loader.load_entities(temp_entities_dir)

        response = client.get("/entities/mark-smith")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Mark Smith"
        assert data["company"] == "AI Branding Academy"

    def test_get_entity_not_found(self, client):
        """Test getting non-existent entity."""
        response = client.get("/entities/nobody")
        assert response.status_code == 404

    def test_reload_entities(self, client):
        """Test reloading entities."""
        response = client.post("/entities/reload")
        assert response.status_code == 200
        assert "reloaded" in response.json()["message"].lower()


class TestCompleteTaskInSource:
    """Test POST /tasks/{task_id}/complete endpoint."""

    def test_complete_not_found(self, client):
        """Complete non-existent task returns 404."""
        response = client.post("/tasks/nonexistent/complete")
        assert response.status_code == 404

    def test_complete_success(self, client):
        """Complete task marks it done in source and locally."""
        # Add a task (id format: "source:source_id")
        db = TestSessionLocal()
        task = Task(
            id="clickup:abc123",
            source="clickup",
            title="Test Task",
            status="todo",
            assignee="ivan",
            url="http://test",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.complete.return_value = WriteResult(
                success=True, message="Task completed in ClickUp"
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/tasks/clickup:abc123/complete")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "ClickUp" in data["message"]
            # Verify correct source_id was extracted
            mock_writer.complete.assert_called_once_with("abc123")

    def test_complete_conflict_detected(self, client):
        """Complete returns conflict when task already done in source."""
        db = TestSessionLocal()
        task = Task(
            id="github:456",
            source="github",
            title="Already Done",
            status="todo",
            assignee="ivan",
            url="http://test",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.complete.return_value = WriteResult(
                success=True,
                message="Issue already closed",
                conflict=True,
                current_state="closed",
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/tasks/github:456/complete")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["conflict"] is True
            assert data["current_state"] == "closed"


class TestAddCommentToSource:
    """Test POST /tasks/{task_id}/comment endpoint."""

    def test_comment_not_found(self, client):
        """Comment on non-existent task returns 404."""
        response = client.post("/tasks/nonexistent/comment", json={"text": "Hello"})
        assert response.status_code == 404

    def test_comment_success(self, client):
        """Comment is added to source."""
        db = TestSessionLocal()
        task = Task(
            id="clickup:xyz789",
            source="clickup",
            title="Commentable",
            status="todo",
            assignee="ivan",
            url="http://test",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.comment.return_value = WriteResult(
                success=True, message="Comment added to ClickUp"
            )
            mock_get_writer.return_value = mock_writer

            response = client.post(
                "/tasks/clickup:xyz789/comment", json={"text": "My comment"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            mock_writer.comment.assert_called_once_with("xyz789", "My comment")


class TestCreateTaskInSource:
    """Test POST /tasks endpoint."""

    def test_create_success(self, client):
        """Create task in ClickUp succeeds."""
        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.create.return_value = WriteResult(
                success=True,
                message="Task created in ClickUp",
                source_id="new-task-id",
            )
            mock_get_writer.return_value = mock_writer

            response = client.post(
                "/tasks?source=clickup",
                json={"title": "New Task", "description": "Details"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["source_id"] == "new-task-id"

    def test_create_github(self, client):
        """Create task in GitHub succeeds."""
        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.create.return_value = WriteResult(
                success=True,
                message="Issue created in GitHub",
                source_id="123",
            )
            mock_get_writer.return_value = mock_writer

            response = client.post(
                "/tasks?source=github",
                json={"title": "Bug Report"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_create_unknown_source(self, client):
        """Create with unknown source returns 400."""
        response = client.post(
            "/tasks?source=jira",
            json={"title": "Task"},
        )
        assert response.status_code == 400


class TestGitHubWebhook:
    """Test POST /webhooks/github endpoint."""

    def test_github_issue_closed(self, client):
        """GitHub webhook closes task when issue closed."""
        # Add a task
        db = TestSessionLocal()
        task = Task(
            id="github:42",
            source="github",
            title="Test Issue",
            status="todo",
            assignee="ivan",
            url="http://github.com/test/42",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {
            "action": "closed",
            "issue": {"number": 42, "title": "Test Issue"},
        }

        # No signature verification (secret not configured)
        with patch("app.main.settings") as mock_settings:
            mock_settings.github_webhook_secret = ""

            response = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "issues"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["event"] == "issues"
            assert data["action"] == "closed"

        # Verify task was marked done
        db = TestSessionLocal()
        updated_task = db.query(Task).filter(Task.id == "github:42").first()
        assert updated_task.status == "done"
        db.close()

    def test_github_issue_reopened(self, client):
        """GitHub webhook reopens task when issue reopened."""
        db = TestSessionLocal()
        task = Task(
            id="github:43",
            source="github",
            title="Reopened Issue",
            status="done",
            assignee="ivan",
            url="http://github.com/test/43",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {
            "action": "reopened",
            "issue": {"number": 43},
        }

        with patch("app.main.settings") as mock_settings:
            mock_settings.github_webhook_secret = ""

            response = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "issues"},
            )
            assert response.status_code == 200

        db = TestSessionLocal()
        updated_task = db.query(Task).filter(Task.id == "github:43").first()
        assert updated_task.status == "todo"
        db.close()

    def test_github_invalid_signature(self, client):
        """GitHub webhook rejects invalid signature."""
        payload = {"action": "closed", "issue": {"number": 1}}
        body = json.dumps(payload).encode()

        with patch("app.main.settings") as mock_settings:
            mock_settings.github_webhook_secret = "test-secret"

            response = client.post(
                "/webhooks/github",
                content=body,
                headers={
                    "X-GitHub-Event": "issues",
                    "X-Hub-Signature-256": "sha256=invalid",
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 401


class TestDoneExecutesAction:
    """Test that /done executes processor task actions."""

    def test_done_executes_github_comment_action(self, client):
        """POST /done should execute action for processor tasks."""
        # Create processor task with action
        db = TestSessionLocal()
        proc_task = Task(
            id="proc-31-abc123",
            source="processor",
            title="Respond to #31",
            status="pending",
            url="https://github.com/markster-exec/project-tracker/issues/31",
            assignee="ivan",
            action={
                "type": "github_comment",
                "issue": 31,
                "repo": "markster-exec/project-tracker",
                "body": "Keep it open.",
            },
            linked_task_id="github:31",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(proc_task)

        # Set as current task
        current = CurrentTask(user_id="ivan", task_id="proc-31-abc123")
        db.add(current)
        db.commit()
        db.close()

        # Mock GitHub writer for action execution
        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            # Mock both comment (for action) and complete (for task completion)
            mock_writer.comment.return_value = WriteResult(
                success=True, message="Comment posted"
            )
            mock_writer.complete.return_value = WriteResult(
                success=True, message="Task completed"
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/done")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Verify the comment action was executed
        mock_writer.comment.assert_called_once_with("31", "Keep it open.")

    def test_done_without_action_skips_execution(self, client):
        """POST /done should skip action execution for non-processor tasks."""
        db = TestSessionLocal()
        task = Task(
            id="clickup:regular123",
            source="clickup",
            title="Regular Task",
            status="todo",
            assignee="ivan",
            url="http://clickup.com/regular123",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        current = CurrentTask(user_id="ivan", task_id="clickup:regular123")
        db.add(current)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = AsyncMock()
            mock_writer.complete.return_value = WriteResult(
                success=True, message="Task completed"
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/done")

        assert response.status_code == 200
        # comment should NOT have been called (no action)
        mock_writer.comment.assert_not_called()
        # but complete SHOULD have been called
        mock_writer.complete.assert_called_once()


class TestClickUpWebhook:
    """Test POST /webhooks/clickup endpoint."""

    def test_clickup_task_completed(self, client):
        """ClickUp webhook marks task done when status changes to complete."""
        db = TestSessionLocal()
        task = Task(
            id="clickup:abc123",
            source="clickup",
            title="ClickUp Task",
            status="todo",
            assignee="ivan",
            url="http://clickup.com/abc123",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {
            "event": "taskStatusUpdated",
            "task_id": "abc123",
            "history_items": [{"after": {"status": "complete"}}],
        }

        with patch("app.main.settings") as mock_settings:
            mock_settings.clickup_webhook_secret = ""

            response = client.post("/webhooks/clickup", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["event"] == "taskStatusUpdated"

        db = TestSessionLocal()
        updated_task = db.query(Task).filter(Task.id == "clickup:abc123").first()
        assert updated_task.status == "done"
        db.close()

    def test_clickup_task_reopened(self, client):
        """ClickUp webhook reopens task when status changes back."""
        db = TestSessionLocal()
        task = Task(
            id="clickup:def456",
            source="clickup",
            title="Reopened ClickUp",
            status="done",
            assignee="ivan",
            url="http://clickup.com/def456",
            is_revenue=False,
            is_blocking_json=[],
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {
            "event": "taskStatusUpdated",
            "task_id": "def456",
            "history_items": [{"after": {"status": "in progress"}}],
        }

        with patch("app.main.settings") as mock_settings:
            mock_settings.clickup_webhook_secret = ""

            response = client.post("/webhooks/clickup", json=payload)
            assert response.status_code == 200

        db = TestSessionLocal()
        updated_task = db.query(Task).filter(Task.id == "clickup:def456").first()
        assert updated_task.status == "todo"
        db.close()

    def test_clickup_invalid_signature(self, client):
        """ClickUp webhook rejects invalid signature."""
        payload = {"event": "taskUpdated", "task_id": "xyz"}
        body = json.dumps(payload).encode()

        with patch("app.main.settings") as mock_settings:
            mock_settings.clickup_webhook_secret = "test-secret"

            response = client.post(
                "/webhooks/clickup",
                content=body,
                headers={
                    "X-Signature": "invalid",
                    "Content-Type": "application/json",
                },
            )
            assert response.status_code == 401
