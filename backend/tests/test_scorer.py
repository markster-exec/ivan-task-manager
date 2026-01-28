"""Tests for the scoring algorithm."""

from datetime import date, timedelta

from app.scorer import (
    calculate_score,
    calculate_urgency,
    get_urgency_label,
    score_and_sort_tasks,
    get_score_breakdown,
)
from app.models import Task


class TestCalculateUrgency:
    """Test urgency calculation based on due dates."""

    def test_no_due_date(self):
        """No due date returns urgency level 1."""
        assert calculate_urgency(None) == 1

    def test_overdue(self):
        """Overdue tasks return urgency level 5."""
        overdue = date.today() - timedelta(days=1)
        assert calculate_urgency(overdue) == 5

    def test_due_today(self):
        """Tasks due today return urgency level 4."""
        assert calculate_urgency(date.today()) == 4

    def test_due_this_week(self):
        """Tasks due within 7 days return urgency level 3."""
        this_week = date.today() + timedelta(days=3)
        assert calculate_urgency(this_week) == 3

    def test_future(self):
        """Tasks due beyond 7 days return urgency level 1."""
        future = date.today() + timedelta(days=14)
        assert calculate_urgency(future) == 1


class TestUrgencyLabel:
    """Test human-readable urgency labels."""

    def test_overdue_label(self):
        """Overdue tasks show 'Overdue' label."""
        overdue = date.today() - timedelta(days=1)
        assert get_urgency_label(overdue) == "Overdue"

    def test_due_today_label(self):
        """Tasks due today show 'Due today' label."""
        assert get_urgency_label(date.today()) == "Due today"

    def test_due_this_week_label(self):
        """Tasks due this week show 'Due this week' label."""
        this_week = date.today() + timedelta(days=3)
        assert get_urgency_label(this_week) == "Due this week"

    def test_no_deadline_label(self):
        """Tasks without due date show 'No deadline' label."""
        assert get_urgency_label(None) == "No deadline"


class TestCalculateScore:
    """Test the complete scoring algorithm."""

    def test_base_score(self, sample_task):
        """Basic task with due today gets urgency score only."""
        score = calculate_score(sample_task)
        # Due today = urgency 4, so 4 * 100 = 400, plus recency bonus
        assert score >= 400

    def test_revenue_bonus(self, revenue_task):
        """Revenue tasks get 1000 point bonus."""
        score = calculate_score(revenue_task)
        assert score >= 1000

    def test_blocking_bonus(self, blocking_task):
        """Blocking tasks get 500 points per person."""
        score = calculate_score(blocking_task)
        # 2 people blocked = 1000 points
        assert score >= 1000

    def test_overdue_urgency(self, overdue_task):
        """Overdue tasks get high urgency score."""
        score = calculate_score(overdue_task)
        # Overdue = urgency 5, so 5 * 100 = 500
        assert score >= 500

    def test_revenue_beats_blocking_one(self, revenue_task, sample_task):
        """Revenue task beats single blocking."""
        sample_task.is_blocking = ["tamas"]
        revenue_score = calculate_score(revenue_task)
        blocking_score = calculate_score(sample_task)
        assert revenue_score > blocking_score

    def test_blocking_two_beats_non_urgent_revenue(self):
        """Blocking 2+ people can beat non-urgent revenue task."""
        revenue = Task(
            id="1",
            source="clickup",
            title="Revenue",
            status="todo",
            assignee="ivan",
            due_date=date.today() + timedelta(days=30),  # Far future
            url="http://test",
            is_revenue=True,
            is_blocking=[],
        )
        blocking = Task(
            id="2",
            source="clickup",
            title="Blocking",
            status="todo",
            assignee="ivan",
            due_date=date.today(),  # Due today
            url="http://test",
            is_revenue=False,
            is_blocking=["tamas", "attila"],
        )
        revenue_score = calculate_score(revenue)
        blocking_score = calculate_score(blocking)
        # Revenue: 1000 + 100 = 1100
        # Blocking: 1000 + 400 = 1400
        assert blocking_score > revenue_score


class TestScoreAndSort:
    """Test task sorting by score."""

    def test_sorts_descending(self, sample_task, revenue_task, blocking_task):
        """Tasks are sorted by score descending."""
        tasks = [sample_task, revenue_task, blocking_task]
        sorted_tasks = score_and_sort_tasks(tasks)

        scores = [t.score for t in sorted_tasks]
        assert scores == sorted(scores, reverse=True)

    def test_revenue_first(self, sample_task, revenue_task):
        """Revenue task comes first."""
        tasks = [sample_task, revenue_task]
        sorted_tasks = score_and_sort_tasks(tasks)
        assert sorted_tasks[0].is_revenue is True


class TestScoreBreakdown:
    """Test score breakdown for display."""

    def test_breakdown_components(self, revenue_task):
        """Breakdown includes all components."""
        revenue_task.score = calculate_score(revenue_task)
        breakdown = get_score_breakdown(revenue_task)

        assert "total" in breakdown
        assert "revenue" in breakdown
        assert "blocking" in breakdown
        assert "urgency" in breakdown
        assert "urgency_label" in breakdown
        assert "recency" in breakdown

    def test_revenue_breakdown(self, revenue_task):
        """Revenue breakdown shows 1000 for revenue tasks."""
        revenue_task.score = calculate_score(revenue_task)
        breakdown = get_score_breakdown(revenue_task)
        assert breakdown["revenue"] == 1000

    def test_blocking_breakdown(self, blocking_task):
        """Blocking breakdown shows 500 per person."""
        blocking_task.score = calculate_score(blocking_task)
        breakdown = get_score_breakdown(blocking_task)
        assert breakdown["blocking"] == 1000  # 2 people * 500
        assert breakdown["blocking_count"] == 2


# Entity context scoring tests


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
    from app.scorer import calculate_score, calculate_score_with_context
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

    # Calculate base score first
    base_score = calculate_score(sample_task)

    # Score with context should be higher
    score = calculate_score_with_context(sample_task, entity, workstream)

    # Should include entity and project bonuses
    # Project urgency 3 * 50 = 150, Entity priority 5 * 25 = 125
    assert score == base_score + 150 + 125


def test_get_score_breakdown_with_context(sample_task):
    """Test breakdown includes entity context."""
    from app.scorer import get_score_breakdown_with_context
    from app.entity_models import Entity, Workstream

    entity = Entity(
        id="mark",
        type="person",
        name="Mark",
        created=date.today(),
        updated=date.today(),
        relationship_type="client",
    )
    workstream = Workstream(
        id="workshop",
        name="Workshop",
        status="active",
        deadline=date.today() + timedelta(days=3),
    )

    breakdown = get_score_breakdown_with_context(sample_task, entity, workstream)

    assert breakdown["entity_name"] == "Mark"
    assert breakdown["workstream_name"] == "Workshop"
    assert breakdown["project_urgency"] == 150  # 3 * 50
    assert breakdown["entity_priority"] == 100  # 4 * 25
