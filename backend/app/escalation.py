"""Smart escalation logic for notifications.

Escalation ladder based on days overdue:
- Day 0: Morning briefing only (no individual notification)
- Day 1: Flagged in briefing (no individual notification)
- Day 2: Afternoon digest (no individual notification)
- Day 3+: Individual DM with buttons
- Day 5+: Escalation prompt
- Day 7+: Final warning
"""

from datetime import date
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session

from .models import Task


def calculate_days_overdue(due_date: Optional[date]) -> int:
    """Calculate how many days a task is overdue.

    Returns:
        Number of days overdue (0 if not overdue or no due date)
    """
    if not due_date:
        return 0

    today = date.today()
    days = (today - due_date).days

    return max(0, days)


def calculate_escalation_level(task: Task) -> int:
    """Calculate escalation level for a task.

    Levels:
        0: Due today or in future (morning briefing only)
        1: 1 day overdue (flagged in briefing)
        2: 2 days overdue (afternoon digest)
        3: 3-4 days overdue (individual DM)
        5: 5-6 days overdue (escalation prompt)
        7: 7+ days overdue (final warning)

    Returns:
        Escalation level (0-7)
    """
    days_overdue = calculate_days_overdue(task.due_date)

    if days_overdue == 0:
        return 0
    elif days_overdue == 1:
        return 1
    elif days_overdue == 2:
        return 2
    elif days_overdue <= 4:
        return 3
    elif days_overdue <= 6:
        return 5
    else:
        return 7


def should_send_individual_notification(task: Task) -> bool:
    """Check if task should get an individual notification.

    Only tasks 3+ days overdue get individual DMs.
    """
    level = calculate_escalation_level(task)
    return level >= 3


def get_escalation_message(level: int) -> str:
    """Get the escalation message prefix based on level.

    Args:
        level: Escalation level (3, 5, or 7)

    Returns:
        Message prefix string
    """
    messages = {
        3: "3 days overdue",
        5: "5 days overdue - should I delegate or kill it?",
        7: "7+ days overdue - removing from active list unless you respond",
    }
    return messages.get(level, f"{level} days overdue")


def group_tasks_by_escalation(tasks: list[Task]) -> dict[int, list[Task]]:
    """Group tasks by their escalation level.

    Args:
        tasks: List of tasks to group

    Returns:
        Dict mapping escalation level to list of tasks
    """
    groups: dict[int, list[Task]] = defaultdict(list)

    for task in tasks:
        level = calculate_escalation_level(task)
        if level >= 3:  # Only group tasks that would get individual notifications
            groups[level].append(task)

    return dict(groups)


def should_consolidate(tasks_at_level: list[Task]) -> bool:
    """Check if tasks at a level should be consolidated.

    3+ tasks at same level → one grouped message.
    """
    return len(tasks_at_level) >= 3


def get_tasks_needing_notification(
    db: Session,
    assignee: str = "ivan",
) -> list[Task]:
    """Get tasks that need escalation notifications.

    Args:
        db: Database session
        assignee: Filter by assignee

    Returns:
        List of tasks needing notification (3+ days overdue, not done)
    """
    tasks = (
        db.query(Task)
        .filter(
            Task.assignee == assignee,
            Task.status != "done",
            Task.due_date.isnot(None),
        )
        .all()
    )

    # Filter to only tasks that should get individual notifications
    return [t for t in tasks if should_send_individual_notification(t)]


def update_escalation_levels(db: Session, tasks: list[Task]) -> None:
    """Update escalation levels for tasks and save to database.

    Args:
        db: Database session
        tasks: Tasks to update
    """
    for task in tasks:
        task.escalation_level = calculate_escalation_level(task)

    db.commit()
