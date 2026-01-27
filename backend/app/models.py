"""SQLAlchemy models for Ivan Task Manager."""

from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Boolean,
    Integer,
    DateTime,
    Date,
    JSON,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, echo=settings.env == "development")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Task(Base):
    """Unified task model aggregating ClickUp and GitHub tasks."""

    __tablename__ = "tasks"

    id = Column(String, primary_key=True)  # "clickup:869bxxud4" or "github:17"
    source = Column(String, nullable=False)  # "clickup" | "github"
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False)  # "todo" | "in_progress" | "done"
    assignee = Column(String, nullable=True)  # "ivan" | "tamas" | "attila"
    due_date = Column(Date, nullable=True)
    url = Column(String, nullable=False)

    # Scoring inputs
    is_revenue = Column(Boolean, default=False)
    is_blocking_json = Column(JSON, default=list)  # List of people blocked
    blocked_by_json = Column(JSON, default=list)  # List of task IDs

    # Computed score
    score = Column(Integer, default=0)

    # Metadata
    last_activity = Column(DateTime, nullable=True)
    source_data = Column(JSON, nullable=True)  # Raw API response
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_blocking(self) -> list[str]:
        return self.is_blocking_json or []

    @is_blocking.setter
    def is_blocking(self, value: list[str]):
        self.is_blocking_json = value

    @property
    def blocked_by(self) -> list[str]:
        return self.blocked_by_json or []

    @blocked_by.setter
    def blocked_by(self, value: list[str]):
        self.blocked_by_json = value


class CurrentTask(Base):
    """Tracks the task Ivan is currently working on."""

    __tablename__ = "current_task"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, default="ivan")
    task_id = Column(String, nullable=True)  # Reference to Task.id
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncState(Base):
    """Tracks sync state for each source."""

    __tablename__ = "sync_state"

    source = Column(String, primary_key=True)  # "clickup" | "github"
    last_sync = Column(DateTime, nullable=True)
    status = Column(
        String, default="pending"
    )  # "pending" | "running" | "success" | "error"
    error_message = Column(Text, nullable=True)


class NotificationLog(Base):
    """Log of sent notifications to avoid duplicates."""

    __tablename__ = "notification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notification_type = Column(
        String, nullable=False
    )  # "instant" | "digest" | "morning"
    task_id = Column(String, nullable=True)
    message_hash = Column(String, nullable=False)  # To dedupe
    sent_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
