"""Tests for the scoring algorithm."""

import pytest
from datetime import date, datetime, timedelta

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
