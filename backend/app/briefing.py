"""Morning briefing generator.

Generates structured morning briefing data:
- Top 3 tasks by score
- Summary stats (total, overdue, due today)
- Calendar placeholder (Phase 4)
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .config import get_settings
from .models import Task
from .scorer import score_and_sort_tasks, get_urgency_label
from .escalation import calculate_days_overdue

settings = get_settings()


@dataclass
class BriefingTask:
    """Task data for briefing display."""

    id: str
    title: str
    url: str
    score: int
    flags: list[str]
    days_overdue: int


@dataclass
class BriefingStats:
    """Summary statistics for briefing."""

    total: int
    overdue: int
    due_today: int
    blocking_people: list[str]


@dataclass
class CalendarEvent:
    """Calendar event placeholder."""

    time: str
    title: str
    source: str = "calendar"


@dataclass
class MorningBriefing:
    """Complete morning briefing data."""

    greeting: str
    location: Optional[str]
    top_tasks: list[BriefingTask]
    stats: BriefingStats
    calendar_events: list[CalendarEvent]
    suggestion: Optional[str]


def get_user_local_time() -> datetime:
    """Get current time in user's timezone."""
    tz = ZoneInfo(settings.user_timezone)
    return datetime.now(tz)


def is_briefing_time() -> bool:
    """Check if current time is the configured briefing time.

    Returns True if within 5 minutes of configured morning_briefing_time.
    """
    local_now = get_user_local_time()
    briefing_hour, briefing_minute = map(int, settings.morning_briefing_time.split(":"))

    # Check if within 5-minute window
    current_minutes = local_now.hour * 60 + local_now.minute
    briefing_minutes = briefing_hour * 60 + briefing_minute

    return abs(current_minutes - briefing_minutes) <= 5


def _build_task_flags(task: Task) -> list[str]:
    """Build flag list for a task."""
    flags = []
    if task.is_revenue:
        flags.append("Revenue")
    if task.is_blocking:
        flags.append(f"Blocking: {', '.join(task.is_blocking)}")

    days_overdue = calculate_days_overdue(task.due_date)
    if days_overdue > 0:
        flags.append(f"{days_overdue}d overdue")
    else:
        flags.append(get_urgency_label(task.due_date))

    return flags


def _get_calendar_placeholder() -> list[CalendarEvent]:
    """Return placeholder calendar events.

    TODO: Phase 4 will implement real Google Calendar integration.
    """
    return [
        CalendarEvent(
            time="--:--",
            title="Calendar integration coming in Phase 4",
            source="placeholder",
        )
    ]


def generate_morning_briefing(
    db: Session,
    assignee: str = "ivan",
    location: Optional[str] = None,
) -> MorningBriefing:
    """Generate morning briefing data.

    Args:
        db: Database session
        assignee: Filter tasks by assignee
        location: Optional location string (e.g., "Los Angeles")

    Returns:
        MorningBriefing with all data for display
    """
    # Get all open tasks for assignee
    tasks = (
        db.query(Task)
        .filter(
            Task.assignee == assignee,
            Task.status != "done",
        )
        .all()
    )

    # Score and sort
    sorted_tasks = score_and_sort_tasks(tasks)

    # Build top 3 tasks
    top_tasks = []
    for task in sorted_tasks[:3]:
        top_tasks.append(
            BriefingTask(
                id=task.id,
                title=task.title,
                url=task.url,
                score=task.score,
                flags=_build_task_flags(task),
                days_overdue=calculate_days_overdue(task.due_date),
            )
        )

    # Calculate stats
    overdue_count = sum(
        1 for t in tasks if t.due_date and calculate_days_overdue(t.due_date) > 0
    )
    due_today_count = sum(1 for t in tasks if t.due_date and t.due_date == date.today())

    blocking_people: set[str] = set()
    for t in tasks:
        if t.is_blocking:
            blocking_people.update(t.is_blocking)

    stats = BriefingStats(
        total=len(tasks),
        overdue=overdue_count,
        due_today=due_today_count,
        blocking_people=sorted(blocking_people),
    )

    # Generate suggestion if many overdue
    suggestion = None
    overdue_3plus = sum(1 for t in tasks if calculate_days_overdue(t.due_date) >= 3)
    if overdue_3plus >= 3:
        suggestion = (
            f"You have {overdue_3plus} tasks overdue 3+ days. "
            "Want me to bulk-defer the non-revenue ones to next week?"
        )

    # Get greeting based on time
    local_time = get_user_local_time()
    hour = local_time.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    return MorningBriefing(
        greeting=greeting,
        location=location,
        top_tasks=top_tasks,
        stats=stats,
        calendar_events=_get_calendar_placeholder(),
        suggestion=suggestion,
    )
