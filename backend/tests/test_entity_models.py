"""Tests for entity Pydantic models."""

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
        workstreams=[Workstream(id="workshop", name="Workshop", status="active")],
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


def test_entity_get_workstream():
    """Test getting workstream by ID."""
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
        workstreams=[
            Workstream(id="ws1", name="Workstream 1", status="active"),
            Workstream(id="ws2", name="Workstream 2", status="planned"),
        ],
    )

    ws = entity.get_workstream("ws2")
    assert ws is not None
    assert ws.id == "ws2"


def test_entity_get_workstream_not_found():
    """Test getting non-existent workstream."""
    from app.entity_models import Entity

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
    )

    assert entity.get_workstream("nonexistent") is None


def test_entity_get_priority_no_relationship():
    """Test priority when relationship_type is None."""
    from app.entity_models import Entity

    entity = Entity(
        id="test",
        type="person",
        name="Test",
        created=date(2026, 1, 28),
        updated=date(2026, 1, 28),
    )
    # Should return default of 2 when no relationship_type
    assert entity.get_priority() == 2
