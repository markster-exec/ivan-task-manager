---
id: phase-4b-implementation-plan
title: Phase 4B Entity Awareness Implementation Plan
type: plan
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [phase-4, entity-awareness, implementation]
---

# Phase 4B: Entity Awareness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add entity awareness so tasks know their context (who, what project, why it matters).

**Architecture:** YAML-based entity registry loaded on startup. Task-entity mapping via explicit tags + manual overrides. Enhanced scoring with project urgency and entity priority. New CLI commands (entity, context, projects) and bot integration.

**Tech Stack:** Python 3, FastAPI, Pydantic, PyYAML, Click, Rich, pytest

---

## Task 1: Create Entity Pydantic Models

**Files:**
- Create: `backend/app/entity_models.py`
- Test: `backend/tests/test_entity_models.py`

**Step 1: Write the failing test**

Create `backend/tests/test_entity_models.py`:

```python
"""Tests for entity Pydantic models."""

import pytest
from datetime import date


def test_workstream_model():
    """Test Workstream model creation."""
    from app.entity_models import Workstream

    ws = Workstream(
        id="workshop",
        name="Workshop Success",
        status="active",
        deadline=date(2026, 2, 15),
        milestone="Live workshop",
        revenue_potential="$10,000+",
    )

    assert ws.id == "workshop"
    assert ws.status == "active"
    assert ws.deadline == date(2026, 2, 15)


def test_workstream_optional_fields():
    """Test Workstream with minimal fields."""
    from app.entity_models import Workstream

    ws = Workstream(id="setup", name="Setup", status="planned")

    assert ws.deadline is None
    assert ws.milestone is None
    assert ws.revenue_potential is None


def test_entity_model():
    """Test Entity model creation."""
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="mark-smith",
        type="person",
        name="Mark Smith",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        tags=["client", "priority"],
        company="AI Branding Academy",
        email="mark@example.com",
        relationship_type="client",
        intention="Showcase client",
        workstreams=[
            Workstream(id="workshop", name="Workshop", status="active")
        ],
        channels={"gdoc": "1byTVc..."},
        context_summary="Building AI Branding Academy.",
    )

    assert entity.id == "mark-smith"
    assert entity.type == "person"
    assert len(entity.workstreams) == 1


def test_entity_get_priority_default():
    """Test priority defaults from relationship_type."""
    from app.entity_models import Entity

    client = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        relationship_type="client",
    )
    assert client.get_priority() == 4

    prospect = Entity(
        id="test2",
        type="person",
        name="Test2",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        relationship_type="prospect",
    )
    assert prospect.get_priority() == 3


def test_entity_get_priority_override():
    """Test priority override."""
    from app.entity_models import Entity

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        relationship_type="client",
        priority=5,
    )
    assert entity.get_priority() == 5


def test_entity_get_active_workstream():
    """Test getting first active workstream."""
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        workstreams=[
            Workstream(id="done", name="Done", status="complete"),
            Workstream(id="active1", name="Active 1", status="active"),
            Workstream(id="active2", name="Active 2", status="active"),
        ],
    )

    ws = entity.get_active_workstream()
    assert ws is not None
    assert ws.id == "active1"


def test_entity_get_active_workstream_none():
    """Test getting active workstream when none active."""
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        workstreams=[
            Workstream(id="done", name="Done", status="complete"),
        ],
    )

    assert entity.get_active_workstream() is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_models.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.entity_models'"

**Step 3: Write minimal implementation**

Create `backend/app/entity_models.py`:

```python
"""Pydantic models for entities (people/companies with context)."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class Workstream(BaseModel):
    """A project or initiative within an entity relationship."""

    id: str
    name: str
    status: Literal["planned", "active", "blocked", "complete"]
    deadline: Optional[date] = None
    milestone: Optional[str] = None
    revenue_potential: Optional[str] = None


class Entity(BaseModel):
    """A person or company Ivan has a relationship with."""

    # Required fields
    id: str
    type: Literal["person", "company"]
    name: str
    created: date
    updated: date
    tags: list[str] = []

    # Optional identity
    company: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None

    # Relationship
    relationship_type: Optional[str] = None
    priority: Optional[int] = None
    intention: Optional[str] = None

    # Workstreams & channels
    workstreams: list[Workstream] = []
    channels: dict[str, str] = {}
    context_summary: Optional[str] = None

    # Relationship type to priority mapping
    _RELATIONSHIP_DEFAULTS = {
        "team": 5,
        "client": 4,
        "investor": 4,
        "prospect": 3,
        "partner": 3,
        "vendor": 1,
        "network": 1,
    }

    def get_priority(self) -> int:
        """Return priority, defaulting from relationship_type."""
        if self.priority is not None:
            return self.priority
        return self._RELATIONSHIP_DEFAULTS.get(self.relationship_type, 2)

    def get_active_workstream(self) -> Optional[Workstream]:
        """Return first active workstream, or None."""
        for ws in self.workstreams:
            if ws.status == "active":
                return ws
        return None

    def get_workstream(self, workstream_id: str) -> Optional[Workstream]:
        """Return workstream by ID, or None."""
        for ws in self.workstreams:
            if ws.id == workstream_id:
                return ws
        return None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_models.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/entity_models.py backend/tests/test_entity_models.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(entity): add Entity and Workstream Pydantic models"
```

---

## Task 2: Create Entity Loader

**Files:**
- Create: `backend/app/entity_loader.py`
- Create: `entities/` directory with example YAML
- Test: `backend/tests/test_entity_loader.py`

**Step 1: Write the failing test**

Create `backend/tests/test_entity_loader.py`:

```python
"""Tests for entity YAML loader."""

import pytest
import tempfile
from pathlib import Path
from datetime import date


@pytest.fixture
def temp_entities_dir():
    """Create a temporary entities directory with test YAML files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        entities_path = Path(tmpdir)

        # Create a test entity
        entity_yaml = """
id: mark-smith
type: person
name: Mark Smith
created: 2026-01-28
updated: 2026-01-28
tags:
  - client
  - priority
company: AI Branding Academy
email: mark@example.com
relationship_type: client
priority: 5
intention: Showcase client

workstreams:
  - id: workshop
    name: Workshop Success
    status: active
    deadline: 2026-02-15
    milestone: Live workshop
    revenue_potential: "$10,000+"

channels:
  gdoc: "1byTVc..."
  github: "markster-exec/project-tracker#16"

context_summary: |
  Building AI Branding Academy.
"""
        (entities_path / "mark-smith.yaml").write_text(entity_yaml)

        # Create another entity
        entity2_yaml = """
id: kyle-stearns
type: person
name: Kyle Stearns
created: 2026-01-28
updated: 2026-01-28
company: Ace Industrial
relationship_type: prospect

workstreams:
  - id: voice-ai
    name: Voice AI Setup
    status: active
    deadline: 2026-02-01
"""
        (entities_path / "kyle-stearns.yaml").write_text(entity2_yaml)

        # Create mappings file
        mappings_yaml = """
task_overrides:
  "clickup:869bxxud4":
    entity: mark-smith
    workstream: workshop
  "github:42":
    entity: kyle-stearns
"""
        (entities_path / "mappings.yaml").write_text(mappings_yaml)

        yield entities_path


def test_load_entities(temp_entities_dir):
    """Test loading entities from YAML files."""
    from app.entity_loader import load_entities, get_all_entities

    load_entities(temp_entities_dir)
    entities = get_all_entities()

    assert len(entities) == 2
    ids = {e.id for e in entities}
    assert "mark-smith" in ids
    assert "kyle-stearns" in ids


def test_get_entity(temp_entities_dir):
    """Test getting a specific entity by ID."""
    from app.entity_loader import load_entities, get_entity

    load_entities(temp_entities_dir)

    mark = get_entity("mark-smith")
    assert mark is not None
    assert mark.name == "Mark Smith"
    assert mark.company == "AI Branding Academy"
    assert mark.get_priority() == 5
    assert len(mark.workstreams) == 1
    assert mark.workstreams[0].deadline == date(2026, 2, 15)


def test_get_entity_not_found(temp_entities_dir):
    """Test getting non-existent entity."""
    from app.entity_loader import load_entities, get_entity

    load_entities(temp_entities_dir)

    assert get_entity("nobody") is None


def test_get_override(temp_entities_dir):
    """Test getting task override mapping."""
    from app.entity_loader import load_entities, get_override

    load_entities(temp_entities_dir)

    # Override with workstream
    override = get_override("clickup:869bxxud4")
    assert override == ("mark-smith", "workshop")

    # Override without workstream
    override = get_override("github:42")
    assert override == ("kyle-stearns", None)

    # No override
    assert get_override("clickup:unknown") is None


def test_reload_entities(temp_entities_dir):
    """Test reloading entities clears cache."""
    from app.entity_loader import load_entities, get_all_entities

    load_entities(temp_entities_dir)
    assert len(get_all_entities()) == 2

    # Remove an entity file
    (temp_entities_dir / "kyle-stearns.yaml").unlink()

    # Reload
    load_entities(temp_entities_dir)
    assert len(get_all_entities()) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_loader.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.entity_loader'"

**Step 3: Write minimal implementation**

Create `backend/app/entity_loader.py`:

```python
"""Load entities from YAML files."""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .entity_models import Entity

logger = logging.getLogger(__name__)

# In-memory cache
_entities: dict[str, Entity] = {}
_mappings: dict[str, dict] = {}


def load_entities(entities_dir: Path) -> None:
    """Load all entity YAML files into memory.

    Args:
        entities_dir: Path to the entities/ directory
    """
    global _entities, _mappings
    _entities = {}
    _mappings = {}

    if not entities_dir.exists():
        logger.warning(f"Entities directory not found: {entities_dir}")
        return

    for yaml_file in entities_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text())

            if yaml_file.name == "mappings.yaml":
                _mappings = data.get("task_overrides", {})
                logger.info(f"Loaded {len(_mappings)} task overrides")
            else:
                entity = Entity(**data)
                _entities[entity.id] = entity
                logger.debug(f"Loaded entity: {entity.id}")

        except Exception as e:
            logger.error(f"Failed to load {yaml_file}: {e}")

    logger.info(f"Loaded {len(_entities)} entities")


def get_entity(entity_id: str) -> Optional[Entity]:
    """Get entity by ID.

    Args:
        entity_id: The entity ID (slug)

    Returns:
        Entity or None if not found
    """
    return _entities.get(entity_id)


def get_all_entities() -> list[Entity]:
    """Get all loaded entities.

    Returns:
        List of all entities
    """
    return list(_entities.values())


def get_override(task_id: str) -> Optional[tuple[str, Optional[str]]]:
    """Get manual override mapping for a task.

    Args:
        task_id: The task ID (e.g., "clickup:869bxxud4")

    Returns:
        Tuple of (entity_id, workstream_id) or None if no override.
        workstream_id may be None if only entity is specified.
    """
    if task_id in _mappings:
        override = _mappings[task_id]
        return (override["entity"], override.get("workstream"))
    return None


def find_entity_by_name(name: str) -> Optional[Entity]:
    """Find entity by name (case-insensitive partial match).

    Args:
        name: Name to search for

    Returns:
        First matching entity or None
    """
    name_lower = name.lower()
    for entity in _entities.values():
        if name_lower in entity.name.lower():
            return entity
        if name_lower in entity.id.lower():
            return entity
    return None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_loader.py -v`

Expected: All tests PASS

**Step 5: Create entities directory with example**

Create `entities/` directory at project root with example entity:

```bash
mkdir -p /Users/ivanivanka/Developer/Work/ivan-task-manager/entities
```

Create `/Users/ivanivanka/Developer/Work/ivan-task-manager/entities/.gitkeep`:

```
# Entity YAML files go here
# See docs/plans/2026-01-28-phase-4b-entity-awareness-design.md for schema
```

Create `/Users/ivanivanka/Developer/Work/ivan-task-manager/entities/mappings.yaml`:

```yaml
# Task-to-entity manual overrides
# Use this for tasks that don't have [CLIENT:x] tags

task_overrides: {}
  # Example:
  # "clickup:869bxxud4":
  #   entity: mark-smith
  #   workstream: workshop
```

**Step 6: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/entity_loader.py backend/tests/test_entity_loader.py entities/
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(entity): add YAML entity loader"
```

---

## Task 3: Create Entity Mapper

**Files:**
- Create: `backend/app/entity_mapper.py`
- Test: `backend/tests/test_entity_mapper.py`

**Step 1: Write the failing test**

Create `backend/tests/test_entity_mapper.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_mapper.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'app.entity_mapper'"

**Step 3: Write minimal implementation**

Create `backend/app/entity_mapper.py`:

```python
"""Map tasks to entities based on tags, titles, and overrides."""

import re
import logging
from typing import Optional

from .models import Task
from .entity_loader import get_entity, get_override

logger = logging.getLogger(__name__)

# Pattern for [CLIENT:entity] or [CLIENT:entity:workstream] in titles
CLIENT_TAG_PATTERN = re.compile(
    r"\[CLIENT:([a-z0-9-]+)(?::([a-z0-9-]+))?\]",
    re.IGNORECASE
)


def parse_client_tag(title: str) -> Optional[tuple[str, Optional[str]]]:
    """Parse [CLIENT:entity:workstream] from task title.

    Args:
        title: Task title

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id may be None.
    """
    match = CLIENT_TAG_PATTERN.search(title)
    if match:
        entity_id = match.group(1).lower()
        workstream_id = match.group(2).lower() if match.group(2) else None
        return (entity_id, workstream_id)
    return None


def parse_clickup_tags(source_data: Optional[dict]) -> Optional[tuple[str, Optional[str]]]:
    """Parse client:entity:workstream from ClickUp tags.

    Args:
        source_data: Raw ClickUp API response

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id may be None.
    """
    if not source_data:
        return None

    tags = source_data.get("tags", [])
    for tag in tags:
        tag_name = tag.get("name", "").lower()
        if tag_name.startswith("client:"):
            parts = tag_name.split(":")
            if len(parts) >= 2:
                entity_id = parts[1]
                workstream_id = parts[2] if len(parts) >= 3 else None
                return (entity_id, workstream_id)

    return None


def resolve_workstream(entity_id: str, workstream_id: Optional[str]) -> Optional[str]:
    """Resolve workstream ID, defaulting to first active if not specified.

    Args:
        entity_id: The entity ID
        workstream_id: The workstream ID (may be None)

    Returns:
        Resolved workstream ID or None
    """
    entity = get_entity(entity_id)
    if not entity:
        return None

    if workstream_id:
        # Verify workstream exists
        if entity.get_workstream(workstream_id):
            return workstream_id
        logger.warning(f"Workstream '{workstream_id}' not found for entity '{entity_id}'")
        # Fall through to default

    # Default to first active workstream
    active = entity.get_active_workstream()
    return active.id if active else None


def map_task_to_entity(task: Task) -> Optional[tuple[str, Optional[str]]]:
    """Map a task to an entity and workstream.

    Priority:
    1. Manual overrides (mappings.yaml)
    2. [CLIENT:entity:workstream] in title
    3. client:entity:workstream ClickUp tag

    Args:
        task: The task to map

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id resolved to first active if not specified.
    """
    # 1. Check manual overrides first
    override = get_override(task.id)
    if override:
        entity_id, workstream_id = override
        if get_entity(entity_id):
            resolved_ws = resolve_workstream(entity_id, workstream_id)
            return (entity_id, resolved_ws)
        logger.warning(f"Override entity '{entity_id}' not found for task '{task.id}'")

    # 2. Parse from title
    title_match = parse_client_tag(task.title)
    if title_match:
        entity_id, workstream_id = title_match
        if get_entity(entity_id):
            resolved_ws = resolve_workstream(entity_id, workstream_id)
            return (entity_id, resolved_ws)
        logger.warning(f"Title entity '{entity_id}' not found for task '{task.id}'")

    # 3. Parse from ClickUp tags
    if task.source == "clickup":
        tag_match = parse_clickup_tags(task.source_data)
        if tag_match:
            entity_id, workstream_id = tag_match
            if get_entity(entity_id):
                resolved_ws = resolve_workstream(entity_id, workstream_id)
                return (entity_id, resolved_ws)
            logger.warning(f"Tag entity '{entity_id}' not found for task '{task.id}'")

    return None
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_entity_mapper.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/entity_mapper.py backend/tests/test_entity_mapper.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(entity): add task-to-entity mapper"
```

---

## Task 4: Enhanced Scoring with Entity Context

**Files:**
- Modify: `backend/app/scorer.py`
- Modify: `backend/tests/test_scorer.py`

**Step 1: Write the failing tests**

Add to `backend/tests/test_scorer.py`:

```python
# Add these tests at the end of the file

def test_calculate_project_urgency_from_workstream():
    """Test project urgency from workstream deadline."""
    from app.scorer import calculate_project_urgency
    from app.entity_models import Workstream

    # Overdue workstream
    overdue_ws = Workstream(
        id="test",
        name="Test",
        status="active",
        deadline=date.today() - timedelta(days=2),
    )
    assert calculate_project_urgency(overdue_ws) == 5

    # Due today
    today_ws = Workstream(
        id="test",
        name="Test",
        status="active",
        deadline=date.today(),
    )
    assert calculate_project_urgency(today_ws) == 4

    # Due this week
    week_ws = Workstream(
        id="test",
        name="Test",
        status="active",
        deadline=date.today() + timedelta(days=3),
    )
    assert calculate_project_urgency(week_ws) == 3

    # Future
    future_ws = Workstream(
        id="test",
        name="Test",
        status="active",
        deadline=date.today() + timedelta(days=30),
    )
    assert calculate_project_urgency(future_ws) == 1


def test_calculate_project_urgency_no_deadline():
    """Test project urgency with no deadline."""
    from app.scorer import calculate_project_urgency
    from app.entity_models import Workstream

    ws = Workstream(id="test", name="Test", status="active")
    assert calculate_project_urgency(ws) == 1


def test_calculate_project_urgency_none():
    """Test project urgency with no workstream."""
    from app.scorer import calculate_project_urgency

    assert calculate_project_urgency(None) == 0


def test_calculate_entity_score():
    """Test entity priority score calculation."""
    from app.scorer import calculate_entity_score
    from app.entity_models import Entity

    # Client (priority 4)
    client = Entity(
        id="test",
        type="person",
        name="Test",
        created=date.today(),
        updated=date.today(),
        relationship_type="client",
    )
    assert calculate_entity_score(client) == 4 * 25  # 100

    # With override priority
    vip = Entity(
        id="test",
        type="person",
        name="Test",
        created=date.today(),
        updated=date.today(),
        relationship_type="client",
        priority=5,
    )
    assert calculate_entity_score(vip) == 5 * 25  # 125


def test_calculate_entity_score_none():
    """Test entity score with no entity."""
    from app.scorer import calculate_entity_score

    assert calculate_entity_score(None) == 0


def test_score_with_entity_context(sample_task):
    """Test full score calculation with entity context."""
    from app.scorer import calculate_score_with_context
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="mark",
        type="person",
        name="Mark",
        created=date.today(),
        updated=date.today(),
        relationship_type="client",
        priority=5,
    )
    workstream = Workstream(
        id="workshop",
        name="Workshop",
        status="active",
        deadline=date.today() + timedelta(days=3),  # Due this week
    )

    # Base score + project urgency (3 * 50 = 150) + entity priority (5 * 25 = 125)
    base_score = sample_task.score or 0
    score = calculate_score_with_context(sample_task, entity, workstream)

    # Should include entity and project bonuses
    assert score > base_score
    # Project urgency 3 * 50 = 150, Entity priority 5 * 25 = 125
    assert score >= base_score + 150 + 125
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_scorer.py::test_calculate_project_urgency_from_workstream -v`

Expected: FAIL with "cannot import name 'calculate_project_urgency' from 'app.scorer'"

**Step 3: Update implementation**

Modify `backend/app/scorer.py` - add these functions after the existing code:

```python
# Add these imports at the top (after existing imports)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .entity_models import Entity, Workstream


def calculate_project_urgency(workstream: "Workstream | None") -> int:
    """Calculate urgency level from workstream deadline.

    Args:
        workstream: The workstream (may be None)

    Returns:
        Urgency level 0-5 (0 if no workstream)
    """
    if not workstream:
        return 0
    return calculate_urgency(workstream.deadline)


def calculate_entity_score(entity: "Entity | None") -> int:
    """Calculate score bonus from entity priority.

    Args:
        entity: The entity (may be None)

    Returns:
        Score bonus (priority * 25, max 125)
    """
    if not entity:
        return 0
    return entity.get_priority() * 25


def calculate_score_with_context(
    task: Task,
    entity: "Entity | None" = None,
    workstream: "Workstream | None" = None,
) -> int:
    """Calculate full score including entity context.

    Score = (Revenue × 1000)
          + (Blocking × 500 × count)
          + (Task Urgency × 100)
          + (Project Urgency × 50)
          + (Entity Priority × 25)
          + Recency

    Args:
        task: The task to score
        entity: Optional entity for priority bonus
        workstream: Optional workstream for project urgency

    Returns:
        Total score
    """
    # Start with base score
    score = calculate_score(task)

    # Add project urgency (workstream deadline)
    project_urgency = calculate_project_urgency(workstream)
    score += project_urgency * 50

    # Add entity priority
    entity_score = calculate_entity_score(entity)
    score += entity_score

    return score


def get_score_breakdown_with_context(
    task: Task,
    entity: "Entity | None" = None,
    workstream: "Workstream | None" = None,
) -> dict:
    """Get detailed breakdown including entity context.

    Args:
        task: The task
        entity: Optional entity
        workstream: Optional workstream

    Returns:
        Dict with all score components
    """
    breakdown = get_score_breakdown(task)

    # Add entity context
    project_urgency = calculate_project_urgency(workstream)
    entity_priority = entity.get_priority() if entity else 0

    breakdown.update({
        "project_urgency": project_urgency * 50,
        "project_urgency_level": project_urgency,
        "entity_priority": entity_priority * 25,
        "entity_priority_level": entity_priority,
        "entity_name": entity.name if entity else None,
        "workstream_name": workstream.name if workstream else None,
        "workstream_deadline": workstream.deadline.isoformat() if workstream and workstream.deadline else None,
    })

    # Recalculate total
    breakdown["total"] = calculate_score_with_context(task, entity, workstream)

    return breakdown
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_scorer.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/scorer.py backend/tests/test_scorer.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(scorer): add entity context to scoring"
```

---

## Task 5: Integrate Entity Loading into App Startup

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`

**Step 1: Update config**

Add to `backend/app/config.py` after existing settings:

```python
    # Entity settings
    entities_dir: str = "entities"
```

**Step 2: Update main.py lifespan**

In `backend/app/main.py`, add import at top:

```python
from pathlib import Path
from .entity_loader import load_entities
```

In the `lifespan` function, after `init_db()`, add:

```python
    # Load entities
    entities_path = Path(settings.entities_dir)
    if not entities_path.is_absolute():
        # Relative to project root (parent of backend/)
        entities_path = Path(__file__).parent.parent.parent / settings.entities_dir
    load_entities(entities_path)
```

**Step 3: Test manually**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -c "from app.main import app; print('OK')"`

Expected: "OK" (no import errors)

**Step 4: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/main.py backend/app/config.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(app): load entities on startup"
```

---

## Task 6: Add Entity API Endpoints

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py` (add entity tests)

**Step 1: Write the failing tests**

Add to `backend/tests/test_api.py`:

```python
# Add these tests

def test_get_entities(client, temp_entities_dir, monkeypatch):
    """Test listing all entities."""
    from app import entity_loader
    entity_loader.load_entities(temp_entities_dir)

    response = client.get("/entities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_entity_by_id(client, temp_entities_dir, monkeypatch):
    """Test getting specific entity."""
    from app import entity_loader
    entity_loader.load_entities(temp_entities_dir)

    response = client.get("/entities/mark-smith")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Mark Smith"


def test_get_entity_not_found(client):
    """Test getting non-existent entity."""
    response = client.get("/entities/nobody")
    assert response.status_code == 404


def test_reload_entities(client, temp_entities_dir):
    """Test reloading entities."""
    response = client.post("/entities/reload")
    assert response.status_code == 200
    assert "reloaded" in response.json()["message"].lower()
```

Add fixture to `backend/tests/conftest.py`:

```python
@pytest.fixture
def temp_entities_dir():
    """Create temporary entities directory for testing."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        entities_path = Path(tmpdir)

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
    name: Workshop
    status: active
""")

        yield entities_path
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_api.py::test_get_entities -v`

Expected: FAIL (404 - endpoint doesn't exist)

**Step 3: Add API endpoints**

Add to `backend/app/main.py`:

```python
# Add import
from .entity_loader import get_entity, get_all_entities, load_entities, find_entity_by_name
from .entity_models import Entity as EntityModel


# Add Pydantic response models
class EntitySummaryResponse(BaseModel):
    id: str
    name: str
    type: str
    company: Optional[str]
    relationship_type: Optional[str]
    priority: int
    active_workstream: Optional[str]
    task_count: int = 0


class WorkstreamResponse(BaseModel):
    id: str
    name: str
    status: str
    deadline: Optional[str]
    milestone: Optional[str]
    revenue_potential: Optional[str]


class EntityDetailResponse(BaseModel):
    id: str
    name: str
    type: str
    created: str
    updated: str
    tags: list[str]
    company: Optional[str]
    email: Optional[str]
    linkedin: Optional[str]
    phone: Optional[str]
    relationship_type: Optional[str]
    priority: int
    intention: Optional[str]
    workstreams: list[WorkstreamResponse]
    channels: dict[str, str]
    context_summary: Optional[str]


# Add endpoints
@app.get("/entities", response_model=list[EntitySummaryResponse])
async def list_entities():
    """List all entities with summary info."""
    entities = get_all_entities()
    return [
        EntitySummaryResponse(
            id=e.id,
            name=e.name,
            type=e.type,
            company=e.company,
            relationship_type=e.relationship_type,
            priority=e.get_priority(),
            active_workstream=e.get_active_workstream().name if e.get_active_workstream() else None,
        )
        for e in entities
    ]


@app.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity_detail(entity_id: str):
    """Get full entity details."""
    entity = get_entity(entity_id)
    if not entity:
        # Try fuzzy match
        entity = find_entity_by_name(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return EntityDetailResponse(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        created=entity.created.isoformat(),
        updated=entity.updated.isoformat(),
        tags=entity.tags,
        company=entity.company,
        email=entity.email,
        linkedin=entity.linkedin,
        phone=entity.phone,
        relationship_type=entity.relationship_type,
        priority=entity.get_priority(),
        intention=entity.intention,
        workstreams=[
            WorkstreamResponse(
                id=ws.id,
                name=ws.name,
                status=ws.status,
                deadline=ws.deadline.isoformat() if ws.deadline else None,
                milestone=ws.milestone,
                revenue_potential=ws.revenue_potential,
            )
            for ws in entity.workstreams
        ],
        channels=entity.channels,
        context_summary=entity.context_summary,
    )


@app.post("/entities/reload")
async def reload_entities():
    """Reload entities from YAML files."""
    entities_path = Path(settings.entities_dir)
    if not entities_path.is_absolute():
        entities_path = Path(__file__).parent.parent.parent / settings.entities_dir
    load_entities(entities_path)
    return {"message": f"Reloaded {len(get_all_entities())} entities"}
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/test_api.py -v`

Expected: All tests PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/main.py backend/tests/test_api.py backend/tests/conftest.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(api): add entity endpoints"
```

---

## Task 7: Add Entity CLI Commands

**Files:**
- Modify: `cli/ivan/__init__.py`

**Step 1: Add entity command**

Add to `cli/ivan/__init__.py`:

```python
@cli.command()
@click.argument("name")
def entity(name: str):
    """Show entity details and tasks."""
    data = api_get(f"/entities/{name}")

    console.print()
    console.print(f"[bold]{data['name']}[/bold] — {data.get('company', 'N/A')}")
    if data.get("email"):
        console.print(f"  Email: {data['email']}")
    if data.get("phone"):
        console.print(f"  Phone: {data['phone']}")
    console.print(f"  Type: {data.get('relationship_type', 'N/A')} | Priority: {data['priority']}")
    console.print()

    if data.get("intention"):
        console.print(f"[bold]Intention:[/bold] {data['intention']}")
        console.print()

    # Workstreams
    if data.get("workstreams"):
        console.print("[bold]Workstreams:[/bold]")
        for ws in data["workstreams"]:
            status_color = {
                "active": "green",
                "blocked": "red",
                "planned": "yellow",
                "complete": "dim",
            }.get(ws["status"], "white")
            deadline = f" — due {ws['deadline']}" if ws.get("deadline") else ""
            revenue = f" ({ws['revenue_potential']})" if ws.get("revenue_potential") else ""
            console.print(f"  [{status_color}][{ws['status']}][/{status_color}] {ws['name']}{deadline}{revenue}")
        console.print()

    # Channels
    if data.get("channels"):
        console.print("[bold]Where to work:[/bold]")
        for key, value in data["channels"].items():
            # Format URLs nicely
            if key == "gdoc":
                url = f"https://docs.google.com/document/d/{value}"
            elif key == "github" and not value.startswith("http"):
                url = f"https://github.com/{value}"
            else:
                url = value
            console.print(f"  {key.capitalize()}: [cyan]{url}[/cyan]")
        console.print()

    # Context
    if data.get("context_summary"):
        console.print("[bold]Context:[/bold]")
        console.print(f"  {data['context_summary'].strip()}")


@cli.command()
def projects():
    """Show all entities grouped by workstream status."""
    data = api_get("/entities")

    if not data:
        console.print("[dim]No entities found.[/dim]")
        return

    console.print()
    console.print("[bold]ACTIVE WORKSTREAMS[/bold]")
    console.print()

    active_found = False
    for entity in sorted(data, key=lambda e: -e["priority"]):
        if entity.get("active_workstream"):
            active_found = True
            console.print(f"[bold]{entity['name']}[/bold] ({entity.get('company', 'N/A')})")
            console.print(f"  → {entity['active_workstream']}")
            console.print()

    if not active_found:
        console.print("[dim]No active workstreams[/dim]")
        console.print()


@cli.command()
@click.argument("task_number", type=int, required=False)
def context(task_number: int = None):
    """Show entity context for current or specified task."""
    if task_number:
        # Get task by number from list
        tasks = api_get("/tasks")
        if task_number > len(tasks) or task_number < 1:
            console.print(f"[red]Task #{task_number} not found[/red]")
            return
        task = tasks[task_number - 1]
    else:
        # Get current task
        data = api_get("/next")
        if not data.get("task"):
            console.print("[dim]No current task.[/dim]")
            return
        task = data["task"]

    console.print()
    console.print(f"[bold]{task['title']}[/bold]")
    console.print(f"[cyan]{task['url']}[/cyan]")
    console.print()

    # TODO: Add entity context once task-entity mapping is wired up
    breakdown = task.get("score_breakdown", {})
    if breakdown.get("entity_name"):
        console.print(f"[bold]Entity:[/bold] {breakdown['entity_name']}")
        if breakdown.get("workstream_name"):
            deadline = f" — due {breakdown['workstream_deadline']}" if breakdown.get("workstream_deadline") else ""
            console.print(f"[bold]Workstream:[/bold] {breakdown['workstream_name']}{deadline}")
    else:
        console.print("[dim]No entity context for this task.[/dim]")
```

**Step 2: Test manually**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && ivan projects`

Expected: Shows "No entities found" or empty active workstreams (since no entities are loaded yet)

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add cli/ivan/__init__.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(cli): add entity, projects, context commands"
```

---

## Task 8: Wire Entity Context into Task Display

**Files:**
- Modify: `backend/app/main.py` - update task endpoints to include entity context
- Modify: `cli/ivan/__init__.py` - update task display

**Step 1: Update main.py to compute entity context**

Add helper function to `backend/app/main.py`:

```python
from .entity_mapper import map_task_to_entity
from .scorer import get_score_breakdown_with_context, calculate_score_with_context


def enrich_task_with_entity(task: Task) -> tuple[Task, dict]:
    """Add entity context to task and return enriched breakdown.

    Returns:
        Tuple of (task with updated score, enriched breakdown dict)
    """
    mapping = map_task_to_entity(task)
    if mapping:
        entity_id, workstream_id = mapping
        entity = get_entity(entity_id)
        workstream = entity.get_workstream(workstream_id) if entity and workstream_id else None

        # Recalculate score with entity context
        task.score = calculate_score_with_context(task, entity, workstream)
        breakdown = get_score_breakdown_with_context(task, entity, workstream)
    else:
        breakdown = get_score_breakdown(task)

    return task, breakdown
```

Update the `get_tasks` endpoint to use enriched context:

```python
@app.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(db: Session = Depends(get_db)):
    """Get all tasks sorted by priority score."""
    tasks = db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()

    # Enrich with entity context and sort
    enriched = []
    for task in tasks:
        task, breakdown = enrich_task_with_entity(task)
        enriched.append((task, breakdown))

    # Sort by enriched score
    enriched.sort(key=lambda x: x[0].score, reverse=True)

    return [
        TaskResponse(
            id=t.id,
            source=t.source,
            title=t.title,
            description=t.description,
            status=t.status,
            assignee=t.assignee,
            due_date=t.due_date.isoformat() if t.due_date else None,
            url=t.url,
            score=t.score,
            is_revenue=t.is_revenue,
            is_blocking=t.is_blocking,
            score_breakdown=breakdown,
        )
        for t, breakdown in enriched
    ]
```

Do the same for `/next` endpoint.

**Step 2: Update CLI display**

In `cli/ivan/__init__.py`, update `format_task` to show entity context:

```python
def format_task(task: dict, show_context: bool = True) -> Panel:
    """Format a task as a rich Panel."""
    breakdown = task.get("score_breakdown", {})
    flags = []

    if task.get("is_revenue"):
        flags.append("[green]Revenue[/green]")
    if task.get("is_blocking"):
        flags.append(f"[yellow]Blocking: {', '.join(task['is_blocking'])}[/yellow]")
    flags.append(f"[blue]{breakdown.get('urgency_label', 'Unknown')}[/blue]")

    content = Text()
    content.append(f"Score: {task.get('score', 0)}", style="bold")
    content.append(f" | {' | '.join(flags)}\n", style="dim")

    # Entity context
    if breakdown.get("entity_name"):
        ws_info = ""
        if breakdown.get("workstream_name"):
            ws_info = f" — {breakdown['workstream_name']}"
            if breakdown.get("workstream_deadline"):
                ws_info += f" by {breakdown['workstream_deadline']}"
        content.append(f"→ {breakdown['entity_name']}{ws_info}\n", style="magenta")

    content.append("\n")

    # Task URL
    content.append(f"Task: {task.get('url', 'No URL')}\n", style="cyan underline")

    # Entity channels (if available)
    # TODO: Add channel URLs from entity

    return Panel(
        content,
        title=f"[bold]{task.get('title', 'Untitled')}[/bold]",
        subtitle=f"[dim]{task.get('source', 'unknown')}:{task.get('id', '?').split(':')[-1]}[/dim]",
        border_style="green" if task.get("is_revenue") else "blue",
    )
```

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/main.py cli/ivan/__init__.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat: wire entity context into task display"
```

---

## Task 9: Add Bot Entity Commands

**Files:**
- Modify: `backend/app/bot.py`
- Modify: `backend/app/slack_blocks.py`

**Step 1: Add entity handler to bot.py**

Add to `backend/app/bot.py`:

```python
from .entity_loader import find_entity_by_name, get_all_entities


async def handle_entity(user_id: str, entity_name: str) -> dict:
    """Get entity information.

    Returns:
        dict with 'text' and 'blocks'
    """
    entity = find_entity_by_name(entity_name)
    if not entity:
        return {"text": f"❓ Entity '{entity_name}' not found."}

    # Build response
    text = f"*{entity.name}* — {entity.company or 'N/A'}"

    blocks = [
        slack_blocks.section(f"*{entity.name}* — {entity.company or 'N/A'}"),
    ]

    if entity.intention:
        blocks.append(slack_blocks.context(f"Intention: {entity.intention}"))

    # Active workstream
    active_ws = entity.get_active_workstream()
    if active_ws:
        deadline = f" — due {active_ws.deadline}" if active_ws.deadline else ""
        blocks.append(slack_blocks.section(f"*Active:* {active_ws.name}{deadline}"))

    # Channels
    if entity.channels:
        channel_lines = []
        for key, value in entity.channels.items():
            if key == "gdoc":
                url = f"https://docs.google.com/document/d/{value}"
            elif key == "github" and not value.startswith("http"):
                url = f"https://github.com/{value}"
            else:
                url = value
            channel_lines.append(f"<{url}|{key.capitalize()}>")
        blocks.append(slack_blocks.context(" · ".join(channel_lines)))

    return {"text": text, "blocks": blocks}


async def handle_projects(user_id: str) -> dict:
    """List all entities with active workstreams.

    Returns:
        dict with 'text' and 'blocks'
    """
    entities = get_all_entities()
    active = [e for e in entities if e.get_active_workstream()]

    if not active:
        return {"text": "No active workstreams."}

    text = "Active Workstreams"
    blocks = [slack_blocks.section("*Active Workstreams*"), slack_blocks.divider()]

    for entity in sorted(active, key=lambda e: -e.get_priority()):
        ws = entity.get_active_workstream()
        deadline = f" — due {ws.deadline}" if ws.deadline else ""
        blocks.append(
            slack_blocks.section(f"*{entity.name}* ({entity.company or 'N/A'})\n→ {ws.name}{deadline}")
        )

    return {"text": text, "blocks": blocks}
```

**Step 2: Add to command patterns**

Update `COMMAND_PATTERNS` in `bot.py`:

```python
COMMAND_PATTERNS = [
    # ... existing patterns ...
    (r"\b(projects|workstreams)\b", handle_projects),
    # Entity pattern needs special handling for the name
]
```

Update `route_message` to handle entity queries:

```python
async def route_message(text: str, user_id: str) -> Optional[dict]:
    """Route message to appropriate handler."""
    text_lower = text.lower().strip()

    # Check for entity query first
    entity_match = re.search(r"(?:entity|what'?s happening with|status of)\s+(\w+)", text_lower)
    if entity_match:
        return await handle_entity(user_id, entity_match.group(1))

    # ... rest of routing logic ...
```

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/bot.py backend/app/slack_blocks.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(bot): add entity and projects commands"
```

---

## Task 10: Add Example Entity and Documentation

**Files:**
- Create: `entities/example.yaml.template`
- Update: `docs/plans/2026-01-28-phase-4b-entity-awareness-design.md` (mark complete)

**Step 1: Create example template**

Create `entities/example.yaml.template`:

```yaml
# Example entity file - copy and customize
# See docs/plans/2026-01-28-phase-4b-entity-awareness-design.md for full schema

id: firstname-lastname          # Unique slug (lowercase, hyphens)
type: person                    # person | company
name: First Last                # Display name
created: 2026-01-28             # ISO date
updated: 2026-01-28             # ISO date
tags:
  - client
  - priority

# Optional identity
company: Company Name
email: email@example.com
# linkedin: https://linkedin.com/in/...
# phone: "+1-555-..."

# Relationship
relationship_type: client       # client|prospect|partner|investor|team|vendor|network
# priority: 5                   # Override (1-5, default from relationship_type)
intention: "One sentence about what we're trying to achieve"

# Workstreams (projects/initiatives)
workstreams:
  - id: main-project
    name: Main Project
    status: active              # planned|active|blocked|complete
    deadline: 2026-02-15
    # milestone: "Launch"
    # revenue_potential: "$10,000+"

# Cross-references (where to work)
channels:
  # gdoc: "document-id-here"
  # github: "org/repo#issue"
  # clickup: "task-id"
  # slack: "#channel-name"

# Context for AI
context_summary: |
  2-3 sentences about this relationship.
  What matters, what's the current focus.
```

**Step 2: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add entities/example.yaml.template
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "docs: add entity example template"
```

---

## Task 11: Run Full Test Suite and Fix Issues

**Step 1: Run all tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager/backend && python -m pytest tests/ -v`

**Step 2: Fix any failures**

Address any test failures that arise.

**Step 3: Commit fixes**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add -A
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "fix: address test failures"
```

---

## Task 12: Update STATE.md and Create PR

**Step 1: Update STATE.md**

Update with Phase 4B completion status.

**Step 2: Push branch and create PR**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager push -u origin issue-2-entity-awareness
gh pr create --repo markster-exec/ivan-task-manager --title "[CORE] Phase 4B: Entity Awareness" --body "$(cat <<'EOF'
## Summary
- Add entity awareness so tasks know their context (who, what project, why it matters)
- YAML-based entity registry with workstreams
- Task-entity mapping via explicit tags + manual overrides
- Enhanced scoring with project urgency and entity priority
- New CLI commands: entity, projects, context
- Bot integration for entity queries

Closes #2

## Test plan
- [ ] Create test entity YAML file
- [ ] Verify task with [CLIENT:x] tag links to entity
- [ ] Verify `ivan next` shows entity context
- [ ] Verify `ivan entity <name>` shows full details
- [ ] Verify `ivan projects` lists active workstreams
- [ ] Verify bot responds to "what's happening with X"

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Summary

| Task | Description | Tests |
|------|-------------|-------|
| 1 | Entity Pydantic models | test_entity_models.py |
| 2 | YAML entity loader | test_entity_loader.py |
| 3 | Task-entity mapper | test_entity_mapper.py |
| 4 | Enhanced scoring | test_scorer.py |
| 5 | App startup integration | Manual |
| 6 | Entity API endpoints | test_api.py |
| 7 | CLI commands | Manual |
| 8 | Wire into task display | Manual |
| 9 | Bot commands | Manual |
| 10 | Example template | N/A |
| 11 | Full test suite | All tests |
| 12 | PR | N/A |

**Estimated commits:** 12

---

*Plan created: 2026-01-28*
