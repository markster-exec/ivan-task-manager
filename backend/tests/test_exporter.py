"""Tests for OfflineExporter."""

import pytest
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

from app.models import Task
from app.exporter import OfflineExporter, ExportResult


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory for export tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_tasks(db_session):
    """Create sample tasks in the database."""
    tasks = [
        Task(
            id="clickup:123",
            source="clickup",
            title="Active Task 1",
            description="Description 1",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="https://app.clickup.com/t/123",
            is_revenue=True,
            is_blocking_json=["attila"],
            blocked_by_json=[],
            score=85,
            last_activity=datetime.utcnow(),
            synced_at=datetime.utcnow(),
        ),
        Task(
            id="github:42",
            source="github",
            title="Active Task 2",
            description="Description 2",
            status="in_progress",
            assignee="ivan",
            due_date=date.today() + timedelta(days=2),
            url="https://github.com/org/repo/issues/42",
            is_revenue=False,
            is_blocking_json=[],
            blocked_by_json=["clickup:456"],
            score=60,
            last_activity=datetime.utcnow() - timedelta(hours=5),
            synced_at=datetime.utcnow(),
        ),
        Task(
            id="clickup:999",
            source="clickup",
            title="Done Task",
            description="Already complete",
            status="done",
            assignee="ivan",
            due_date=date.today() - timedelta(days=1),
            url="https://app.clickup.com/t/999",
            is_revenue=False,
            is_blocking_json=[],
            blocked_by_json=[],
            score=0,
            last_activity=datetime.utcnow() - timedelta(days=1),
            synced_at=datetime.utcnow(),
        ),
    ]
    for task in tasks:
        db_session.add(task)
    db_session.commit()
    return tasks


class TestExportResult:
    """Test ExportResult dataclass."""

    def test_export_result_creation(self):
        """Test creating ExportResult."""
        result = ExportResult(
            success=True,
            message="Export complete",
            tasks_count=10,
            entities_count=5,
        )
        assert result.success is True
        assert result.message == "Export complete"
        assert result.tasks_count == 10
        assert result.entities_count == 5


class TestOfflineExporter:
    """Test OfflineExporter class."""

    def test_export_creates_bundle_directory(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that export creates bundle directory structure."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        assert result.success is True
        assert temp_output_dir.exists()
        assert (temp_output_dir / "tasks.db").exists()
        assert (temp_output_dir / "entities").is_dir()
        assert (temp_output_dir / "briefs").is_dir()
        assert (temp_output_dir / "MANIFEST.md").exists()

    def test_export_copies_non_done_tasks(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that only non-done tasks are exported."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        assert result.success is True
        assert result.tasks_count == 2  # Only the two non-done tasks

        # Verify tasks in SQLite
        conn = sqlite3.connect(temp_output_dir / "tasks.db")
        cursor = conn.execute("SELECT id, title, status FROM tasks")
        rows = cursor.fetchall()
        conn.close()

        assert len(rows) == 2
        ids = [row[0] for row in rows]
        assert "clickup:123" in ids
        assert "github:42" in ids
        assert "clickup:999" not in ids  # Done task excluded

    def test_export_sqlite_schema(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that exported SQLite has correct schema."""
        exporter = OfflineExporter(db_session)
        exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        conn = sqlite3.connect(temp_output_dir / "tasks.db")
        cursor = conn.execute("PRAGMA table_info(tasks)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            "id": "TEXT",
            "source": "TEXT",
            "title": "TEXT",
            "description": "TEXT",
            "status": "TEXT",
            "assignee": "TEXT",
            "due_date": "TEXT",
            "url": "TEXT",
            "is_revenue": "INTEGER",
            "is_blocking": "TEXT",
            "blocked_by": "TEXT",
            "score": "INTEGER",
            "last_activity": "TEXT",
            "synced_at": "TEXT",
            "entity_id": "TEXT",
            "workstream_id": "TEXT",
        }

        for col, col_type in expected_columns.items():
            assert col in columns, f"Missing column: {col}"
            assert (
                columns[col] == col_type
            ), f"Wrong type for {col}: expected {col_type}, got {columns[col]}"

    def test_export_copies_entity_files(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that entity YAML files are copied."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        assert result.success is True
        assert result.entities_count == 1  # mark-smith.yaml from fixture

        entities_output = temp_output_dir / "entities"
        assert (entities_output / "mark-smith.yaml").exists()

    def test_export_creates_manifest(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that MANIFEST.md contains correct metadata."""
        exporter = OfflineExporter(db_session)
        exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        manifest = (temp_output_dir / "MANIFEST.md").read_text()
        assert "# Export Manifest" in manifest
        assert "Tasks: 2" in manifest
        assert "Entities: 1" in manifest
        assert "Exported at:" in manifest

    def test_export_preserves_task_data(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that task data is correctly preserved in export."""
        exporter = OfflineExporter(db_session)
        exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        conn = sqlite3.connect(temp_output_dir / "tasks.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM tasks WHERE id = 'clickup:123'")
        row = dict(cursor.fetchone())
        conn.close()

        assert row["source"] == "clickup"
        assert row["title"] == "Active Task 1"
        assert row["description"] == "Description 1"
        assert row["status"] == "todo"
        assert row["assignee"] == "ivan"
        assert row["url"] == "https://app.clickup.com/t/123"
        assert row["is_revenue"] == 1
        assert row["score"] == 85
        # is_blocking should be JSON-encoded
        assert "attila" in row["is_blocking"]

    def test_export_without_entities_dir(
        self, db_session, temp_output_dir, sample_tasks
    ):
        """Test export when no entities directory is provided."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=None)

        assert result.success is True
        assert result.tasks_count == 2
        assert result.entities_count == 0
        assert (temp_output_dir / "entities").is_dir()  # Directory still created

    def test_export_creates_parent_directories(
        self, db_session, temp_entities_dir, sample_tasks
    ):
        """Test that export creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "output" / "sync"
            exporter = OfflineExporter(db_session)
            result = exporter.export(nested_path, entities_dir=temp_entities_dir)

            assert result.success is True
            assert nested_path.exists()
            assert (nested_path / "tasks.db").exists()

    def test_export_empty_database(
        self, db_session, temp_output_dir, temp_entities_dir
    ):
        """Test export with no tasks in database."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        assert result.success is True
        assert result.tasks_count == 0
        assert (temp_output_dir / "tasks.db").exists()

    def test_export_returns_correct_counts(
        self, db_session, temp_output_dir, temp_entities_dir, sample_tasks
    ):
        """Test that export returns correct task and entity counts."""
        exporter = OfflineExporter(db_session)
        result = exporter.export(temp_output_dir, entities_dir=temp_entities_dir)

        assert result.tasks_count == 2  # 2 non-done tasks
        assert result.entities_count == 1  # 1 entity file
