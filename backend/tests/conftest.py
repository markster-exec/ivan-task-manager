"""Pytest configuration and fixtures."""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Task


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_task():
    """Create a sample task for testing."""
    return Task(
        id="clickup:123",
        source="clickup",
        title="Test Task",
        description="Test description",
        status="todo",
        assignee="ivan",
        due_date=date.today(),
        url="https://app.clickup.com/t/123",
        is_revenue=False,
        is_blocking=[],
        last_activity=datetime.utcnow(),
    )


@pytest.fixture
def revenue_task():
    """Create a revenue task for testing."""
    return Task(
        id="clickup:456",
        source="clickup",
        title="Revenue Task",
        description="Client deal",
        status="todo",
        assignee="ivan",
        due_date=date.today() + timedelta(days=1),
        url="https://app.clickup.com/t/456",
        is_revenue=True,
        is_blocking=[],
        last_activity=datetime.utcnow(),
    )


@pytest.fixture
def blocking_task():
    """Create a blocking task for testing."""
    return Task(
        id="clickup:789",
        source="clickup",
        title="Blocking Task",
        description="Blocking others",
        status="todo",
        assignee="ivan",
        due_date=date.today() + timedelta(days=3),
        url="https://app.clickup.com/t/789",
        is_revenue=False,
        is_blocking=["tamas", "attila"],
        last_activity=datetime.utcnow(),
    )


@pytest.fixture
def overdue_task():
    """Create an overdue task for testing."""
    return Task(
        id="github:42",
        source="github",
        title="Overdue Task",
        description="Past due",
        status="todo",
        assignee="ivan",
        due_date=date.today() - timedelta(days=2),
        url="https://github.com/org/repo/issues/42",
        is_revenue=False,
        is_blocking=[],
        last_activity=datetime.utcnow() - timedelta(days=3),
    )
