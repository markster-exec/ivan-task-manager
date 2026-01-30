"""Offline exporter for ivan-os sync.

Exports tasks to a SQLite bundle for offline use.
"""

import json
import logging
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .models import Task
from .entity_mapper import map_task_to_entity

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of an export operation."""

    success: bool
    message: str
    tasks_count: int
    entities_count: int


class OfflineExporter:
    """Export tasks to SQLite bundle for ivan-os offline sync."""

    SQLITE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        assignee TEXT,
        due_date TEXT,
        url TEXT NOT NULL,
        is_revenue INTEGER DEFAULT 0,
        is_blocking TEXT,
        blocked_by TEXT,
        score INTEGER DEFAULT 0,
        last_activity TEXT,
        synced_at TEXT,
        entity_id TEXT,
        workstream_id TEXT
    )
    """

    def __init__(self, db_session: Session):
        """Initialize exporter with database session.

        Args:
            db_session: SQLAlchemy session for reading tasks
        """
        self.db = db_session

    def export(
        self,
        output_path: Path,
        entities_dir: Optional[Path] = None,
        include_briefs: bool = True,
    ) -> ExportResult:
        """Export tasks and entities to a bundle directory.

        Args:
            output_path: Directory to create bundle in
            entities_dir: Optional path to entity YAML files
            include_briefs: Whether to create briefs directory (for future use)

        Returns:
            ExportResult with success status and counts
        """
        try:
            # Convert to Path if string
            output_path = Path(output_path)

            # Create output directory structure
            output_path.mkdir(parents=True, exist_ok=True)
            (output_path / "entities").mkdir(exist_ok=True)
            (output_path / "pending").mkdir(exist_ok=True)
            (output_path / "outbox").mkdir(exist_ok=True)
            if include_briefs:
                (output_path / "briefs").mkdir(exist_ok=True)

            # Export tasks to SQLite
            tasks_count = self._export_tasks(output_path / "tasks.db")

            # Copy entity files
            entities_count = self._copy_entities(output_path / "entities", entities_dir)

            # Export pending processor tasks
            pending_count = self._export_pending_tasks(output_path / "pending")

            # Create manifest
            self._create_manifest(
                output_path, tasks_count, entities_count, pending_count
            )

            message = f"Exported {tasks_count} tasks, {entities_count} entities, {pending_count} pending"
            logger.info(message)

            return ExportResult(
                success=True,
                message=message,
                tasks_count=tasks_count,
                entities_count=entities_count,
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ExportResult(
                success=False,
                message=f"Export failed: {e}",
                tasks_count=0,
                entities_count=0,
            )

    def _export_tasks(self, db_path: Path) -> int:
        """Export non-done tasks to SQLite database.

        Args:
            db_path: Path to create SQLite database

        Returns:
            Number of tasks exported
        """
        # Remove existing database if present
        if db_path.exists():
            db_path.unlink()

        # Create new database
        conn = sqlite3.connect(db_path)
        conn.execute(self.SQLITE_SCHEMA)

        # Query non-done tasks
        tasks = self.db.query(Task).filter(Task.status != "done").all()

        # Insert tasks
        for task in tasks:
            # Get entity mapping
            entity_id = None
            workstream_id = None
            mapping = map_task_to_entity(task)
            if mapping:
                entity_id, workstream_id = mapping

            conn.execute(
                """
                INSERT INTO tasks (
                    id, source, title, description, status, assignee,
                    due_date, url, is_revenue, is_blocking, blocked_by,
                    score, last_activity, synced_at, entity_id, workstream_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.source,
                    task.title,
                    task.description,
                    task.status,
                    task.assignee,
                    task.due_date.isoformat() if task.due_date else None,
                    task.url,
                    1 if task.is_revenue else 0,
                    json.dumps(task.is_blocking or []),
                    json.dumps(task.blocked_by or []),
                    task.score or 0,
                    task.last_activity.isoformat() if task.last_activity else None,
                    task.synced_at.isoformat() if task.synced_at else None,
                    entity_id,
                    workstream_id,
                ),
            )

        conn.commit()
        conn.close()

        return len(tasks)

    def _copy_entities(self, output_dir: Path, entities_dir: Optional[Path]) -> int:
        """Copy entity YAML files to output directory.

        Args:
            output_dir: Output entities directory
            entities_dir: Source entities directory

        Returns:
            Number of entity files copied
        """
        if not entities_dir or not entities_dir.exists():
            return 0

        count = 0
        for yaml_file in entities_dir.glob("*.yaml"):
            # Skip mappings.yaml (internal file)
            if yaml_file.name == "mappings.yaml":
                continue

            shutil.copy2(yaml_file, output_dir / yaml_file.name)
            count += 1

        return count

    def _export_pending_tasks(self, output_dir: Path) -> int:
        """Export processor tasks as markdown files for offline review.

        Args:
            output_dir: Output pending directory

        Returns:
            Number of pending tasks exported
        """
        # Query processor tasks
        tasks = (
            self.db.query(Task)
            .filter(Task.source == "processor", Task.status == "pending")
            .all()
        )

        count = 0
        for i, task in enumerate(tasks, 1):
            if not task.action:
                continue

            # Build markdown content
            action = task.action
            issue_num = action.get("issue", "?")

            content = f"""---
task_id: {task.id}
github_issue: {issue_num}
repo: {action.get('repo', 'markster-exec/project-tracker')}
action_type: {action.get('type', 'unknown')}
status: {task.status}
linked_task: {task.linked_task_id or ''}
---

# {task.title}

## Context

**URL:** {task.url}
**Linked Task:** {task.linked_task_id or 'None'}

## Description

{task.description or 'No description'}

## Draft Response

{action.get('body', '')}

## Decision

- [ ] approve
- [ ] approve with edits (modify draft above)
- [ ] reject
- [ ] convert to manual task
"""

            filename = f"{i:03d}-respond-{issue_num}.md"
            (output_dir / filename).write_text(content)
            count += 1

        return count

    def _create_manifest(
        self,
        output_path: Path,
        tasks_count: int,
        entities_count: int,
        pending_count: int = 0,
    ) -> None:
        """Create MANIFEST.md with export metadata.

        Args:
            output_path: Bundle output directory
            tasks_count: Number of tasks exported
            entities_count: Number of entities copied
            pending_count: Number of pending processor tasks exported
        """
        manifest = f"""# Export Manifest

Exported at: {datetime.utcnow().isoformat()}Z

## Summary

- Tasks: {tasks_count}
- Entities: {entities_count}
- Pending reviews: {pending_count}

## Contents

- `tasks.db` - SQLite database with active tasks
- `entities/` - Entity YAML files
- `pending/` - Processor tasks for offline review
- `outbox/` - Place decisions here for import
- `briefs/` - Brief documents (future use)

## Offline Workflow

1. Review files in `pending/`
2. Mark decisions (approve/reject/edit)
3. Place `decisions.json` in `outbox/`
4. Run `ivan import` when back online

## Schema

```sql
{self.SQLITE_SCHEMA.strip()}
```
"""
        (output_path / "MANIFEST.md").write_text(manifest)
