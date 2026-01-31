"""Tests for morning briefing generator."""

from datetime import date, timedelta

from app.briefing import (
    generate_morning_briefing,
    _build_task_flags,
    _get_calendar_placeholder,
)
from app.models import Task


class TestBuildTaskFlags:
    """Test flag building for briefing tasks."""

    def test_revenue_flag(self):
        """Revenue tasks get Revenue flag."""
        task = Task(
            id="1",
            source="test",
            title="Test",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
            is_revenue=True,
        )
        flags = _build_task_flags(task)
        assert "Revenue" in flags

    def test_blocking_flag(self):
        """Blocking tasks show who's blocked."""
        task = Task(
            id="1",
            source="test",
            title="Test",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
            is_blocking=["tamas", "attila"],
        )
        flags = _build_task_flags(task)
        assert any("Blocking" in f for f in flags)
        assert any("tamas" in f for f in flags)

    def test_overdue_flag(self):
        """Overdue tasks show days overdue."""
        task = Task(
            id="1",
            source="test",
            title="Test",
            status="todo",
            assignee="ivan",
            due_date=date.today() - timedelta(days=3),
            url="http://test",
        )
        flags = _build_task_flags(task)
        assert any("3d overdue" in f for f in flags)


class TestCalendarPlaceholder:
    """Test calendar placeholder."""

    def test_returns_placeholder(self):
        """Returns placeholder event for Phase 4."""
        events = _get_calendar_placeholder()
        assert len(events) == 1
        assert events[0].source == "placeholder"
        assert "Phase 4" in events[0].title


class TestGenerateMorningBriefing:
    """Test full briefing generation."""

    def test_empty_tasks(self, db_session):
        """Empty task list returns empty briefing."""
        briefing = generate_morning_briefing(db_session)
        assert briefing.stats.total == 0
        assert len(briefing.top_tasks) == 0

    def test_top_3_tasks(self, db_session):
        """Returns top 3 tasks by score."""
        # Create 5 tasks with varying scores using different factors
        # Revenue tasks get +1000, blocking gets +500/person
        tasks_data = [
            ("Task A", False, [], date.today()),  # Score ~400 (due today)
            (
                "Task B",
                False,
                [],
                date.today() - timedelta(days=1),
            ),  # Score ~500 (overdue)
            (
                "Task C",
                True,
                [],
                date.today() + timedelta(days=7),
            ),  # Score ~1100 (revenue)
            ("Task D", False, ["tamas"], date.today()),  # Score ~900 (blocking 1)
            (
                "Task E",
                False,
                ["tamas", "attila"],
                date.today(),
            ),  # Score ~1400 (blocking 2)
        ]
        for i, (title, is_revenue, blocking, due) in enumerate(tasks_data):
            task = Task(
                id=f"test:{i}",
                source="test",
                title=title,
                status="todo",
                assignee="ivan",
                due_date=due,
                url="http://test",
                is_revenue=is_revenue,
                is_blocking=blocking,
            )
            db_session.add(task)
        db_session.commit()

        briefing = generate_morning_briefing(db_session)

        assert len(briefing.top_tasks) == 3
        # Highest scoring task (Task E, blocking 2) should be first
        assert briefing.top_tasks[0].title == "Task E"

    def test_stats_calculation(self, db_session):
        """Stats are calculated correctly."""
        # 1 overdue, 1 due today, 1 future
        overdue = Task(
            id="overdue",
            source="test",
            title="Overdue",
            status="todo",
            assignee="ivan",
            due_date=date.today() - timedelta(days=2),
            url="http://test",
        )
        due_today = Task(
            id="today",
            source="test",
            title="Today",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
        )
        future = Task(
            id="future",
            source="test",
            title="Future",
            status="todo",
            assignee="ivan",
            due_date=date.today() + timedelta(days=7),
            url="http://test",
        )
        db_session.add_all([overdue, due_today, future])
        db_session.commit()

        briefing = generate_morning_briefing(db_session)

        assert briefing.stats.total == 3
        assert briefing.stats.overdue == 1
        assert briefing.stats.due_today == 1

    def test_blocking_people(self, db_session):
        """Blocking people are aggregated."""
        task1 = Task(
            id="1",
            source="test",
            title="Task 1",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
            is_blocking=["tamas"],
        )
        task2 = Task(
            id="2",
            source="test",
            title="Task 2",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
            is_blocking=["attila", "tamas"],
        )
        db_session.add_all([task1, task2])
        db_session.commit()

        briefing = generate_morning_briefing(db_session)

        assert set(briefing.stats.blocking_people) == {"tamas", "attila"}

    def test_suggestion_for_many_overdue(self, db_session):
        """Suggestion appears when 3+ tasks are 3+ days overdue."""
        for i in range(4):
            task = Task(
                id=f"overdue:{i}",
                source="test",
                title=f"Overdue {i}",
                status="todo",
                assignee="ivan",
                due_date=date.today() - timedelta(days=5),  # 5 days overdue
                url="http://test",
            )
            db_session.add(task)
        db_session.commit()

        briefing = generate_morning_briefing(db_session)

        assert briefing.suggestion is not None
        assert "4 tasks" in briefing.suggestion

    def test_location_passed_through(self, db_session):
        """Location is included in briefing."""
        briefing = generate_morning_briefing(db_session, location="Los Angeles")
        assert briefing.location == "Los Angeles"

    def test_filters_by_assignee(self, db_session):
        """Only tasks for specified assignee are included."""
        ivan_task = Task(
            id="ivan",
            source="test",
            title="Ivan Task",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
        )
        tamas_task = Task(
            id="tamas",
            source="test",
            title="Tamas Task",
            status="todo",
            assignee="tamas",
            due_date=date.today(),
            url="http://test",
        )
        db_session.add_all([ivan_task, tamas_task])
        db_session.commit()

        briefing = generate_morning_briefing(db_session, assignee="ivan")

        assert briefing.stats.total == 1
        assert briefing.top_tasks[0].title == "Ivan Task"

    def test_excludes_done_tasks(self, db_session):
        """Done tasks are not included."""
        open_task = Task(
            id="open",
            source="test",
            title="Open",
            status="todo",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
        )
        done_task = Task(
            id="done",
            source="test",
            title="Done",
            status="done",
            assignee="ivan",
            due_date=date.today(),
            url="http://test",
        )
        db_session.add_all([open_task, done_task])
        db_session.commit()

        briefing = generate_morning_briefing(db_session)

        assert briefing.stats.total == 1
