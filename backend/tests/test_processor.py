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
