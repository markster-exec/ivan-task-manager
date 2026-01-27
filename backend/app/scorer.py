"""Task scoring and prioritization logic.

Scoring Algorithm:
    Score = (Revenue × 1000) + (Blocking × 500) + (Urgency × 100) + Recency

Where:
    - Revenue:  1 if is_revenue else 0
    - Blocking: count of people blocked (×500 each)
    - Urgency:  5 if overdue, 4 if due today, 3 if due this week, 1 otherwise
    - Recency:  1 if activity in last 24h else 0
"""

from datetime import date, datetime, timedelta
from typing import Optional

from .models import Task


def calculate_score(task: Task) -> int:
    """Calculate priority score for a task.

    Higher score = higher priority.
    Revenue tasks always win, but blocking 2+ people can outrank non-urgent revenue.
    """
    score = 0

    # Revenue multiplier (1000 points)
    if task.is_revenue:
        score += 1000

    # Blocking multiplier (500 points per person)
    blocking_count = len(task.is_blocking) if task.is_blocking else 0
    score += blocking_count * 500

    # Urgency multiplier (100 points × urgency level)
    urgency = calculate_urgency(task.due_date)
    score += urgency * 100

    # Recency bonus (1 point if active in last 24h)
    if task.last_activity:
        if datetime.utcnow() - task.last_activity < timedelta(hours=24):
            score += 1

    return score


def calculate_urgency(due_date: Optional[date]) -> int:
    """Calculate urgency level based on due date.

    Returns:
        5 if overdue
        4 if due today
        3 if due this week
        1 otherwise (or no due date)
    """
    if not due_date:
        return 1

    today = date.today()
    days_until_due = (due_date - today).days

    if days_until_due < 0:
        return 5  # Overdue
    elif days_until_due == 0:
        return 4  # Due today
    elif days_until_due <= 7:
        return 3  # Due this week
    else:
        return 1  # Future


def get_urgency_label(due_date: Optional[date]) -> str:
    """Get human-readable urgency label."""
    urgency = calculate_urgency(due_date)
    labels = {
        5: "Overdue",
        4: "Due today",
        3: "Due this week",
        1: "No deadline" if not due_date else "Future",
    }
    return labels.get(urgency, "Unknown")


def score_and_sort_tasks(tasks: list[Task]) -> list[Task]:
    """Score all tasks and return sorted by priority (highest first)."""
    for task in tasks:
        task.score = calculate_score(task)

    return sorted(tasks, key=lambda t: t.score, reverse=True)


def get_score_breakdown(task: Task) -> dict:
    """Get detailed breakdown of score components for debugging/display."""
    blocking_count = len(task.is_blocking) if task.is_blocking else 0
    urgency = calculate_urgency(task.due_date)

    recency_bonus = 0
    if task.last_activity:
        if datetime.utcnow() - task.last_activity < timedelta(hours=24):
            recency_bonus = 1

    return {
        "total": task.score,
        "revenue": 1000 if task.is_revenue else 0,
        "blocking": blocking_count * 500,
        "blocking_count": blocking_count,
        "urgency": urgency * 100,
        "urgency_level": urgency,
        "urgency_label": get_urgency_label(task.due_date),
        "recency": recency_bonus,
    }
