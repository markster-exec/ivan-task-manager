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
