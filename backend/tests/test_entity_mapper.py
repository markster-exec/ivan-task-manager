"""Tests for task-to-entity mapping."""

import pytest
import tempfile
from pathlib import Path
from datetime import date

from app.models import Task


@pytest.fixture
def temp_entities_dir():
    """Create a temporary entities directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        entities_path = Path(tmpdir)

        # Mark entity
        (entities_path / "mark-smith.yaml").write_text("""
id: mark-smith
type: person
name: Mark Smith
created: 2026-01-28
updated: 2026-01-28
company: AI Branding Academy
relationship_type: client
workstreams:
  - id: workshop
    name: Workshop Success
    status: active
    deadline: 2026-02-15
  - id: setup
    name: System Setup
    status: complete
""")

        # Kyle entity
        (entities_path / "kyle-stearns.yaml").write_text("""
id: kyle-stearns
type: person
name: Kyle Stearns
created: 2026-01-28
updated: 2026-01-28
company: Ace Industrial
relationship_type: prospect
workstreams:
  - id: voice-ai
    name: Voice AI
    status: active
""")

        # Mappings
        (entities_path / "mappings.yaml").write_text("""
task_overrides:
  "clickup:override1":
    entity: mark-smith
    workstream: workshop
  "clickup:override2":
    entity: kyle-stearns
""")

        yield entities_path


@pytest.fixture
def setup_entities(temp_entities_dir):
    """Load entities before tests."""
    from app.entity_loader import load_entities
    load_entities(temp_entities_dir)


def test_map_from_title_github(setup_entities):
    """Test mapping from [CLIENT:x] in GitHub issue title."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="github:42",
        source="github",
        title="[CLIENT:mark-smith] Write blog post",
        status="todo",
        url="https://github.com/org/repo/issues/42",
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "mark-smith"
    # Should default to first active workstream
    assert workstream_id == "workshop"


def test_map_from_title_with_workstream(setup_entities):
    """Test mapping with workstream in title."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="github:43",
        source="github",
        title="[CLIENT:mark-smith:setup] Review docs",
        status="todo",
        url="https://github.com/org/repo/issues/43",
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "mark-smith"
    assert workstream_id == "setup"


def test_map_from_clickup_tag(setup_entities):
    """Test mapping from ClickUp tags."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="clickup:123",
        source="clickup",
        title="Write proposal",
        status="todo",
        url="https://app.clickup.com/t/123",
        source_data={"tags": [{"name": "client:kyle-stearns"}]},
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "kyle-stearns"
    assert workstream_id == "voice-ai"  # Default to first active


def test_map_from_clickup_tag_with_workstream(setup_entities):
    """Test mapping from ClickUp tag with workstream."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="clickup:124",
        source="clickup",
        title="Schedule call",
        status="todo",
        url="https://app.clickup.com/t/124",
        source_data={"tags": [{"name": "client:mark-smith:workshop"}]},
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "mark-smith"
    assert workstream_id == "workshop"


def test_map_from_override(setup_entities):
    """Test mapping from manual override."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="clickup:override1",
        source="clickup",
        title="Some task without tags",
        status="todo",
        url="https://app.clickup.com/t/override1",
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "mark-smith"
    assert workstream_id == "workshop"


def test_map_from_override_no_workstream(setup_entities):
    """Test mapping from override without workstream."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="clickup:override2",
        source="clickup",
        title="Another task",
        status="todo",
        url="https://app.clickup.com/t/override2",
    )

    result = map_task_to_entity(task)
    assert result is not None
    entity_id, workstream_id = result
    assert entity_id == "kyle-stearns"
    assert workstream_id == "voice-ai"  # Default to first active


def test_map_no_match(setup_entities):
    """Test task with no entity mapping."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="clickup:999",
        source="clickup",
        title="Internal task",
        status="todo",
        url="https://app.clickup.com/t/999",
    )

    result = map_task_to_entity(task)
    assert result is None


def test_map_invalid_entity(setup_entities):
    """Test mapping to non-existent entity."""
    from app.entity_mapper import map_task_to_entity

    task = Task(
        id="github:44",
        source="github",
        title="[CLIENT:nobody] Some task",
        status="todo",
        url="https://github.com/org/repo/issues/44",
    )

    result = map_task_to_entity(task)
    assert result is None
