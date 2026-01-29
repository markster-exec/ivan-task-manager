"""Tests for processor module."""

from app.processor import find_pending_action


class TestFindPendingAction:
    """Tests for finding pending actions in ticket comments."""

    def test_find_pending_question_with_mention(self):
        """Should detect @ivanivanka question in comments."""
        comments = [
            {"author": "atiti", "body": "DNS is set up."},
            {"author": "atiti", "body": "Close this task or keep it open? @ivanivanka"},
        ]

        result = find_pending_action(comments, assignee="ivan")

        assert result is not None
        assert result["type"] == "question"
        assert "close" in result["question"].lower()
        assert result["author"] == "atiti"

    def test_find_pending_question_no_mention(self):
        """Should return None if no @ivanivanka mention."""
        comments = [
            {"author": "atiti", "body": "DNS is set up."},
            {"author": "atiti", "body": "All done here."},
        ]

        result = find_pending_action(comments, assignee="ivan")

        assert result is None

    def test_find_pending_question_already_answered(self):
        """Should return None if Ivan already responded after question."""
        comments = [
            {"author": "atiti", "body": "Close this? @ivanivanka"},
            {"author": "ivanivanka", "body": "Keep it open."},
        ]

        result = find_pending_action(comments, assignee="ivan")

        assert result is None


class TestDraftResponse:
    """Tests for draft response generation."""

    def test_draft_response_simple_question(self):
        """Should draft response for simple yes/no question."""
        from app.processor import draft_response

        context = {
            "question": "Close this task or keep it open? @ivanivanka",
            "entity_name": "Mark De Grasse",
            "workstream": "Email infrastructure",
            "ticket_title": "[CLIENT:Mark] TASK - Domain setup",
            "recent_comments": ["DNS set up", "Mailboxes created"],
        }

        draft = draft_response(context)

        assert draft is not None
        assert len(draft) > 10  # Non-trivial response
        assert isinstance(draft, str)


class TestProcessTicket:
    """Tests for processing tickets."""

    def test_process_ticket_creates_processor_task(self):
        """Should create processor task for ticket with pending question."""
        from unittest.mock import patch

        from app.models import Task
        from app.processor import process_ticket

        # Mock GitHub task
        ticket = Task(
            id="github:31",
            source="github",
            title="[CLIENT:Mark] TASK - Domain setup",
            status="open",
            url="https://github.com/markster-exec/project-tracker/issues/31",
        )

        comments = [
            {"author": "atiti", "body": "Close this? @ivanivanka"},
        ]

        with patch("app.processor.map_task_to_entity") as mock_map:
            with patch("app.processor.get_entity") as mock_entity:
                mock_map.return_value = None  # No entity mapping
                mock_entity.return_value = None

                result = process_ticket(ticket, comments)

        assert result is not None
        assert result["action_type"] == "create_processor_task"
        assert result["task"]["source"] == "processor"
        assert result["task"]["action"]["type"] == "github_comment"
        assert result["task"]["linked_task_id"] == "github:31"

    def test_process_ticket_no_action_needed(self):
        """Should return None when no action needed."""
        from app.models import Task
        from app.processor import process_ticket

        ticket = Task(
            id="github:31",
            source="github",
            title="[CLIENT:Mark] TASK - Domain setup",
            status="open",
            url="https://github.com/markster-exec/project-tracker/issues/31",
        )

        comments = [
            {"author": "atiti", "body": "All done."},
        ]

        result = process_ticket(ticket, comments)

        assert result is None
