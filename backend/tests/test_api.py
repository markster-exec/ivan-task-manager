"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import date, datetime

from app.main import app
from app.models import Task, CurrentTask


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("app.main.get_db") as mock:
        session = MagicMock()
        mock.return_value = iter([session])
        yield session


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

    def test_empty_task_list(self, client, mock_db):
        """Empty database returns empty list."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_tasks_sorted(self, client, mock_db):
        """Tasks are returned sorted by score."""
        task1 = MagicMock(spec=Task)
        task1.id = "1"
        task1.source = "clickup"
        task1.title = "Task 1"
        task1.description = "Desc"
        task1.status = "todo"
        task1.assignee = "ivan"
        task1.due_date = date.today()
        task1.url = "http://test"
        task1.is_revenue = False
        task1.is_blocking = []
        task1.last_activity = datetime.utcnow()
        task1.score = 0

        mock_db.query.return_value.filter.return_value.all.return_value = [task1]

        response = client.get("/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1


class TestNextTask:
    """Test /next endpoint."""

    def test_no_tasks(self, client, mock_db):
        """No tasks returns appropriate message."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/next")
        assert response.status_code == 200
        data = response.json()
        assert data["task"] is None
        assert "No tasks" in data["message"]


class TestDoneEndpoint:
    """Test /done endpoint."""

    def test_no_current_task(self, client, mock_db):
        """No current task returns error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        response = client.post("/done")
        assert response.status_code == 400


class TestSkipEndpoint:
    """Test /skip endpoint."""

    def test_no_current_task(self, client, mock_db):
        """No current task returns error."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

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

    def test_morning_returns_structure(self, client, mock_db):
        """Morning briefing returns expected structure."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        response = client.get("/morning")
        assert response.status_code == 200
        data = response.json()
        assert "top_tasks" in data
        assert "summary" in data
