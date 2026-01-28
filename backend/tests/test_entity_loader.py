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


def test_find_entity_by_name(temp_entities_dir):
    """Test finding entity by partial name match."""
    from app.entity_loader import load_entities, find_entity_by_name

    load_entities(temp_entities_dir)

    # Exact match
    mark = find_entity_by_name("Mark Smith")
    assert mark is not None
    assert mark.id == "mark-smith"

    # Partial match (case-insensitive)
    mark = find_entity_by_name("mark")
    assert mark is not None
    assert mark.id == "mark-smith"

    # ID match
    kyle = find_entity_by_name("kyle-stearns")
    assert kyle is not None

    # No match
    assert find_entity_by_name("nobody") is None
