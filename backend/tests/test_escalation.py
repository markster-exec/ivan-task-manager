"""Tests for escalation logic."""

from datetime import date, timedelta

from app.escalation import (
    calculate_days_overdue,
    calculate_escalation_level,
    should_send_individual_notification,
    get_escalation_message,
    group_tasks_by_escalation,
    should_consolidate,
)
from app.models import Task


def make_task(days_overdue: int) -> Task:
    """Create a task with specified days overdue."""
    due = (
        date.today() - timedelta(days=days_overdue)
        if days_overdue > 0
        else date.today()
    )
    return Task(
        id=f"test:{days_overdue}",
        source="test",
        title=f"Task {days_overdue}d overdue",
        status="todo",
        assignee="ivan",
        due_date=due,
        url="http://test",
    )


class TestCalculateDaysOverdue:
    """Test days overdue calculation."""

    def test_no_due_date(self):
        """No due date returns 0."""
        assert calculate_days_overdue(None) == 0

    def test_due_today(self):
        """Due today returns 0."""
        assert calculate_days_overdue(date.today()) == 0

    def test_future_due_date(self):
        """Future due date returns 0."""
        future = date.today() + timedelta(days=5)
        assert calculate_days_overdue(future) == 0

    def test_one_day_overdue(self):
        """One day overdue returns 1."""
        yesterday = date.today() - timedelta(days=1)
        assert calculate_days_overdue(yesterday) == 1

    def test_five_days_overdue(self):
        """Five days overdue returns 5."""
        past = date.today() - timedelta(days=5)
        assert calculate_days_overdue(past) == 5


class TestCalculateEscalationLevel:
    """Test escalation level calculation."""

    def test_due_today_level_0(self):
        """Task due today gets level 0."""
        task = make_task(0)
        assert calculate_escalation_level(task) == 0

    def test_one_day_overdue_level_1(self):
        """Task 1 day overdue gets level 1."""
        task = make_task(1)
        assert calculate_escalation_level(task) == 1

    def test_two_days_overdue_level_2(self):
        """Task 2 days overdue gets level 2."""
        task = make_task(2)
        assert calculate_escalation_level(task) == 2

    def test_three_days_overdue_level_3(self):
        """Task 3 days overdue gets level 3."""
        task = make_task(3)
        assert calculate_escalation_level(task) == 3

    def test_four_days_overdue_level_3(self):
        """Task 4 days overdue still gets level 3."""
        task = make_task(4)
        assert calculate_escalation_level(task) == 3

    def test_five_days_overdue_level_5(self):
        """Task 5 days overdue gets level 5."""
        task = make_task(5)
        assert calculate_escalation_level(task) == 5

    def test_six_days_overdue_level_5(self):
        """Task 6 days overdue still gets level 5."""
        task = make_task(6)
        assert calculate_escalation_level(task) == 5

    def test_seven_days_overdue_level_7(self):
        """Task 7 days overdue gets level 7."""
        task = make_task(7)
        assert calculate_escalation_level(task) == 7

    def test_ten_days_overdue_level_7(self):
        """Task 10 days overdue still gets level 7."""
        task = make_task(10)
        assert calculate_escalation_level(task) == 7


class TestShouldSendIndividualNotification:
    """Test individual notification threshold."""

    def test_level_0_no_notification(self):
        """Level 0 (due today) gets no individual notification."""
        task = make_task(0)
        assert should_send_individual_notification(task) is False

    def test_level_1_no_notification(self):
        """Level 1 (1 day overdue) gets no individual notification."""
        task = make_task(1)
        assert should_send_individual_notification(task) is False

    def test_level_2_no_notification(self):
        """Level 2 (2 days overdue) gets no individual notification."""
        task = make_task(2)
        assert should_send_individual_notification(task) is False

    def test_level_3_yes_notification(self):
        """Level 3 (3 days overdue) DOES get individual notification."""
        task = make_task(3)
        assert should_send_individual_notification(task) is True

    def test_level_5_yes_notification(self):
        """Level 5 (5 days overdue) DOES get individual notification."""
        task = make_task(5)
        assert should_send_individual_notification(task) is True

    def test_level_7_yes_notification(self):
        """Level 7 (7+ days overdue) DOES get individual notification."""
        task = make_task(7)
        assert should_send_individual_notification(task) is True


class TestGetEscalationMessage:
    """Test escalation message prefixes."""

    def test_level_3_message(self):
        """Level 3 shows simple overdue message."""
        msg = get_escalation_message(3)
        assert "3 days overdue" in msg

    def test_level_5_message(self):
        """Level 5 asks about delegation."""
        msg = get_escalation_message(5)
        assert "delegate or kill" in msg.lower()

    def test_level_7_message(self):
        """Level 7 warns about removal."""
        msg = get_escalation_message(7)
        assert "removing" in msg.lower()


class TestGroupTasksByEscalation:
    """Test task grouping by escalation level."""

    def test_groups_by_level(self):
        """Tasks are grouped by their escalation level."""
        tasks = [
            make_task(3),  # level 3
            make_task(4),  # level 3
            make_task(5),  # level 5
            make_task(7),  # level 7
        ]
        groups = group_tasks_by_escalation(tasks)

        assert 3 in groups
        assert 5 in groups
        assert 7 in groups
        assert len(groups[3]) == 2
        assert len(groups[5]) == 1
        assert len(groups[7]) == 1

    def test_ignores_low_levels(self):
        """Tasks below level 3 are not grouped."""
        tasks = [
            make_task(0),  # level 0
            make_task(1),  # level 1
            make_task(2),  # level 2
            make_task(3),  # level 3
        ]
        groups = group_tasks_by_escalation(tasks)

        # Only level 3 should be in groups
        assert 0 not in groups
        assert 1 not in groups
        assert 2 not in groups
        assert 3 in groups


class TestShouldConsolidate:
    """Test consolidation threshold."""

    def test_two_tasks_no_consolidate(self):
        """2 tasks should not be consolidated."""
        tasks = [make_task(3), make_task(4)]
        assert should_consolidate(tasks) is False

    def test_three_tasks_yes_consolidate(self):
        """3 tasks should be consolidated."""
        tasks = [make_task(3), make_task(4), make_task(3)]
        assert should_consolidate(tasks) is True

    def test_five_tasks_yes_consolidate(self):
        """5 tasks should be consolidated."""
        tasks = [make_task(3) for _ in range(5)]
        assert should_consolidate(tasks) is True
