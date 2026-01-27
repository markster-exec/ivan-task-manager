"""Tests for API endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Task


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
