"""Ticket processor for ivan-task-manager.

Analyzes tickets, drafts responses, creates actionable tasks.
"""

import re
import logging
import uuid
from typing import Optional

from .entity_loader import get_entity
from .entity_mapper import map_task_to_entity
from .models import Task

logger = logging.getLogger(__name__)

# Patterns for detecting questions
MENTION_PATTERN = re.compile(r"@ivanivanka", re.IGNORECASE)
QUESTION_PATTERN = re.compile(r"\?")


def find_pending_action(
    comments: list[dict],
    assignee: Optional[str] = None,
) -> Optional[dict]:
    """Find pending action in ticket comments.

    Looks for:
    - @ivanivanka mentions with questions
    - Unanswered requests

    Args:
        comments: List of comment dicts with 'author' and 'body'
        assignee: Ticket assignee (for context)

    Returns:
        Dict with action details or None if no action needed
    """
    if not comments:
        return None

    # Find last @ivanivanka mention with question
    last_question_idx = None
    last_question_comment = None

    for i, comment in enumerate(comments):
        body = comment.get("body", "")
        author = comment.get("author", "")

        # Skip Ivan's own comments
        if author.lower() in ("ivanivanka", "ivan"):
            # If Ivan responded after a question, reset
            if last_question_idx is not None and i > last_question_idx:
                last_question_idx = None
                last_question_comment = None
            continue

        # Check for @mention with question
        if MENTION_PATTERN.search(body) and QUESTION_PATTERN.search(body):
            last_question_idx = i
            last_question_comment = comment

    if last_question_comment:
        return {
            "type": "question",
            "question": last_question_comment["body"],
            "author": last_question_comment["author"],
            "comment_index": last_question_idx,
        }

    return None


def draft_response(context: dict) -> str:
    """Draft a response based on context.

    For now, uses simple heuristics. Future: LLM integration.

    Args:
        context: Dict with question, entity_name, workstream, etc.

    Returns:
        Draft response string
    """
    question = context.get("question", "").lower()
    workstream = context.get("workstream", "")

    # Simple heuristics for common question patterns
    if "close" in question and "open" in question:
        # Close vs keep open decision
        return f"Keep it open for now - we may need to revisit this for {workstream}."

    if "should we" in question or "shall we" in question:
        # Decision question - default to cautious
        return (
            "Let's hold off on this for now. I'll follow up once I have more context."
        )

    if "can you" in question or "could you" in question:
        # Request for action
        return "I'll take a look at this and update the ticket."

    if "thoughts" in question or "opinion" in question:
        # Asking for input
        return "Good question. Let me review and share my thoughts."

    # Default response
    return "Thanks for the update. I'll review and respond shortly."


def process_ticket(ticket: Task, comments: list[dict]) -> Optional[dict]:
    """Process a single ticket and determine action.

    Args:
        ticket: The Task object representing the GitHub issue
        comments: List of comment dicts

    Returns:
        Dict with action_type and task details, or None if no action needed
    """
    # Find what needs doing
    pending = find_pending_action(comments, assignee=ticket.assignee)

    if not pending:
        return None

    # Get entity context
    entity = None
    workstream = None
    mapping = map_task_to_entity(ticket)
    if mapping:
        entity_id, workstream_id = mapping
        entity = get_entity(entity_id)
        if entity:
            workstream = (
                entity.get_workstream(workstream_id)
                if workstream_id
                else entity.get_active_workstream()
            )

    # Build context for response drafting
    context = {
        "question": pending.get("question", ""),
        "entity_name": entity.name if entity else "",
        "workstream": workstream.name if workstream else "",
        "ticket_title": ticket.title,
        "recent_comments": [c.get("body", "")[:100] for c in comments[-5:]],
    }

    # Draft response
    draft = draft_response(context)

    # Extract issue number from URL or ID
    issue_number = (
        ticket.id.replace("github:", "") if ticket.id.startswith("github:") else None
    )
    if not issue_number and ticket.url:
        # Try to extract from URL
        match = re.search(r"/issues/(\d+)", ticket.url)
        if match:
            issue_number = match.group(1)

    # Create processor task
    proc_task_id = f"proc-{issue_number}-{uuid.uuid4().hex[:8]}"

    return {
        "action_type": "create_processor_task",
        "task": {
            "id": proc_task_id,
            "source": "processor",
            "title": f"Respond to #{issue_number}: {pending.get('question', '')[:50]}...",
            "description": (
                f"Question from {pending.get('author', 'unknown')}:\n\n"
                f"{pending.get('question', '')}"
            ),
            "status": "pending",
            "url": ticket.url,
            "action": {
                "type": "github_comment",
                "issue": int(issue_number) if issue_number else None,
                "repo": "markster-exec/project-tracker",
                "body": draft,
            },
            "linked_task_id": ticket.id,
        },
    }
