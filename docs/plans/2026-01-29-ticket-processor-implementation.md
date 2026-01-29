# Ticket Processor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ticket processing capability that analyzes GitHub issues, drafts responses, and creates actionable tasks.

**Architecture:** Processor creates Tasks with `action` field. On `ivan done`, action executes via existing GitHubWriter. Manual work creates ClickUp tasks in Agent Queue.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Click CLI, httpx

---

## Task 1: Add Action Field to Task Model

**Files:**
- Modify: `backend/app/models.py:25-56`
- Test: `backend/tests/test_models.py`

**Step 1: Write failing test for action field**

```python
# backend/tests/test_models.py - add to existing tests

def test_task_action_field():
    """Task should support action JSON field."""
    task = Task(
        id="proc-31-abc",
        source="processor",
        title="Respond to #31",
        status="pending",
        url="https://github.com/markster-exec/project-tracker/issues/31",
        action={
            "type": "github_comment",
            "issue": 31,
            "repo": "markster-exec/project-tracker",
            "body": "Keep it open.",
        },
        linked_task_id="github:31",
    )
    assert task.action["type"] == "github_comment"
    assert task.action["body"] == "Keep it open."
    assert task.linked_task_id == "github:31"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_models.py::test_task_action_field -v`
Expected: FAIL with "TypeError" or "action" not found

**Step 3: Add action and linked_task_id columns to Task model**

```python
# backend/app/models.py - add after line 55 (after notification_state)

    # Processor action (for processor-generated tasks)
    action = Column(JSON, nullable=True)  # {"type": "github_comment", "issue": 31, ...}
    linked_task_id = Column(String, nullable=True)  # Reference to original task
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_models.py::test_task_action_field -v`
Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/models.py backend/tests/test_models.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(models): add action and linked_task_id fields to Task"
```

---

## Task 2: Create Processor Module - Ticket Analysis

**Files:**
- Create: `backend/app/processor.py`
- Test: `backend/tests/test_processor.py`

**Step 1: Write failing test for finding pending questions**

```python
# backend/tests/test_processor.py

import pytest
from app.processor import find_pending_action


def test_find_pending_question_with_mention():
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


def test_find_pending_question_no_mention():
    """Should return None if no @ivanivanka mention."""
    comments = [
        {"author": "atiti", "body": "DNS is set up."},
        {"author": "atiti", "body": "All done here."},
    ]

    result = find_pending_action(comments, assignee="ivan")

    assert result is None


def test_find_pending_question_already_answered():
    """Should return None if Ivan already responded after question."""
    comments = [
        {"author": "atiti", "body": "Close this? @ivanivanka"},
        {"author": "ivanivanka", "body": "Keep it open."},
    ]

    result = find_pending_action(comments, assignee="ivan")

    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py -v`
Expected: FAIL with "ModuleNotFoundError" or "cannot import name"

**Step 3: Implement find_pending_action**

```python
# backend/app/processor.py

"""Ticket processor for ivan-task-manager.

Analyzes tickets, drafts responses, creates actionable tasks.
"""

import re
import logging
from typing import Optional

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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/processor.py backend/tests/test_processor.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(processor): add find_pending_action for question detection"
```

---

## Task 3: Processor - Draft Response Generation

**Files:**
- Modify: `backend/app/processor.py`
- Test: `backend/tests/test_processor.py`

**Step 1: Write failing test for draft generation**

```python
# backend/tests/test_processor.py - add to existing

def test_draft_response_simple_question():
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py::test_draft_response_simple_question -v`
Expected: FAIL

**Step 3: Implement draft_response**

```python
# backend/app/processor.py - add after find_pending_action

def draft_response(context: dict) -> str:
    """Draft a response based on context.

    For now, uses simple heuristics. Future: LLM integration.

    Args:
        context: Dict with question, entity_name, workstream, etc.

    Returns:
        Draft response string
    """
    question = context.get("question", "").lower()
    entity_name = context.get("entity_name", "")
    workstream = context.get("workstream", "")

    # Simple heuristics for common question patterns
    if "close" in question and "open" in question:
        # Close vs keep open decision
        return f"Keep it open for now - we may need to revisit this for {workstream}."

    if "should we" in question or "shall we" in question:
        # Decision question - default to cautious
        return "Let's hold off on this for now. I'll follow up once I have more context."

    if "can you" in question or "could you" in question:
        # Request for action
        return "I'll take a look at this and update the ticket."

    if "thoughts" in question or "opinion" in question:
        # Asking for input
        return "Good question. Let me review and share my thoughts."

    # Default response
    return "Thanks for the update. I'll review and respond shortly."
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py::test_draft_response_simple_question -v`
Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/processor.py backend/tests/test_processor.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(processor): add draft_response with simple heuristics"
```

---

## Task 4: Processor - Process Single Ticket

**Files:**
- Modify: `backend/app/processor.py`
- Test: `backend/tests/test_processor.py`

**Step 1: Write failing test for process_ticket**

```python
# backend/tests/test_processor.py - add

from unittest.mock import Mock, patch

def test_process_ticket_creates_processor_task():
    """Should create processor task for ticket with pending question."""
    from app.processor import process_ticket
    from app.models import Task

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

    with patch("app.processor.get_entity") as mock_entity:
        mock_entity.return_value = Mock(
            name="Mark De Grasse",
            get_active_workstream=lambda: Mock(name="Email infrastructure"),
        )

        result = process_ticket(ticket, comments)

    assert result is not None
    assert result["action_type"] == "create_processor_task"
    assert result["task"]["source"] == "processor"
    assert result["task"]["action"]["type"] == "github_comment"
    assert result["task"]["linked_task_id"] == "github:31"


def test_process_ticket_no_action_needed():
    """Should return None when no action needed."""
    from app.processor import process_ticket
    from app.models import Task

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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py::test_process_ticket_creates_processor_task -v`
Expected: FAIL

**Step 3: Implement process_ticket**

```python
# backend/app/processor.py - add after draft_response

from .entity_loader import get_entity
from .entity_mapper import map_task_to_entity
from .models import Task
import uuid


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
            workstream = entity.get_workstream(workstream_id) if workstream_id else entity.get_active_workstream()

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
    issue_number = ticket.id.replace("github:", "") if ticket.id.startswith("github:") else None
    if not issue_number and ticket.url:
        # Try to extract from URL
        import re
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
            "description": f"Question from {pending.get('author', 'unknown')}:\n\n{pending.get('question', '')}",
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
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_processor.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/processor.py backend/tests/test_processor.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(processor): add process_ticket to analyze and create tasks"
```

---

## Task 5: API Endpoint - /process

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Step 1: Write failing test for /process endpoint**

```python
# backend/tests/test_api.py - add to existing

def test_process_endpoint(client, db_session):
    """POST /process should process tickets and create processor tasks."""
    # Create a GitHub task
    from app.models import Task
    task = Task(
        id="github:99",
        source="github",
        title="[TEST] Test ticket",
        status="open",
        url="https://github.com/markster-exec/project-tracker/issues/99",
        assignee="ivan",
    )
    db_session.add(task)
    db_session.commit()

    # Mock the GitHub comments fetch
    with patch("app.main.fetch_github_comments") as mock_fetch:
        mock_fetch.return_value = [
            {"author": "atiti", "body": "Should we close this? @ivanivanka"},
        ]

        response = client.post("/process")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["processed"] >= 0
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_api.py::test_process_endpoint -v`
Expected: FAIL (endpoint not found)

**Step 3: Add /process endpoint and helper**

```python
# backend/app/main.py - add imports at top
from .processor import process_ticket

# Add after other response models (around line 80)
class ProcessResponse(BaseModel):
    success: bool
    processed: int
    created_tasks: int
    manual_tasks: int
    message: str


# Add helper function to fetch GitHub comments
async def fetch_github_comments(issue_number: int) -> list[dict]:
    """Fetch comments for a GitHub issue."""
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.github.com/repos/{settings.github_repo}/issues/{issue_number}/comments",
            headers={
                "Authorization": f"token {settings.github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        if response.status_code == 200:
            data = response.json()
            return [
                {"author": c.get("user", {}).get("login", ""), "body": c.get("body", "")}
                for c in data
            ]
    return []


# Add endpoint (after other endpoints)
@app.post("/process", response_model=ProcessResponse)
async def process_tickets(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Process open tickets and create actionable tasks.

    Analyzes GitHub tickets, drafts responses for questions,
    and creates processor tasks or ClickUp tasks as needed.
    """
    # Get open GitHub tasks
    github_tasks = (
        db.query(Task)
        .filter(Task.source == "github", Task.status != "done")
        .limit(limit)
        .all()
    )

    processed = 0
    created_tasks = 0
    manual_tasks = 0

    for task in github_tasks:
        # Extract issue number
        issue_number = task.id.replace("github:", "")
        if not issue_number.isdigit():
            continue

        # Fetch comments
        comments = await fetch_github_comments(int(issue_number))

        # Process ticket
        result = process_ticket(task, comments)
        processed += 1

        if result and result.get("action_type") == "create_processor_task":
            # Create processor task in database
            proc_task_data = result["task"]
            proc_task = Task(
                id=proc_task_data["id"],
                source=proc_task_data["source"],
                title=proc_task_data["title"],
                description=proc_task_data.get("description"),
                status=proc_task_data["status"],
                url=proc_task_data["url"],
                action=proc_task_data.get("action"),
                linked_task_id=proc_task_data.get("linked_task_id"),
                assignee="ivan",
            )
            db.add(proc_task)
            created_tasks += 1

        elif result and result.get("action_type") == "create_manual_task":
            manual_tasks += 1
            # TODO: Create ClickUp task in Agent Queue

    db.commit()

    return ProcessResponse(
        success=True,
        processed=processed,
        created_tasks=created_tasks,
        manual_tasks=manual_tasks,
        message=f"Processed {processed} tickets: {created_tasks} drafts ready, {manual_tasks} need manual work",
    )
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_api.py::test_process_endpoint -v`
Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/main.py backend/tests/test_api.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(api): add /process endpoint for ticket processing"
```

---

## Task 6: CLI Command - ivan process

**Files:**
- Modify: `cli/ivan/__init__.py`

**Step 1: Add process command to CLI**

```python
# cli/ivan/__init__.py - add after export command (around line 545)

@cli.command()
@click.option("--limit", "-l", default=50, help="Max tickets to process")
@click.option("--dry-run", is_flag=True, help="Show what would be processed without creating tasks")
def process(limit: int, dry_run: bool):
    """Process tickets and create actionable tasks."""
    console.print()

    if dry_run:
        console.print("[yellow]DRY RUN - no tasks will be created[/yellow]")
        console.print()

    with console.status("[bold blue]Processing tickets...", spinner="dots"):
        if dry_run:
            # For dry run, just list what would be processed
            data = api_get("/tasks")
            github_tasks = [t for t in data if t.get("source") == "github"]

            console.print(f"[dim]Would process {len(github_tasks[:limit])} GitHub tickets[/dim]")
            return

        result = api_post(f"/process?limit={limit}")

    if result.get("success"):
        console.print(f"[green]✓[/green] {result.get('message', 'Processing complete')}")
        console.print()
        console.print(f"  Processed: {result.get('processed', 0)} tickets")
        console.print(f"  Drafts ready: {result.get('created_tasks', 0)}")
        console.print(f"  Manual tasks: {result.get('manual_tasks', 0)}")
        console.print()

        if result.get("created_tasks", 0) > 0:
            console.print("[dim]Run [bold]ivan next[/bold] to review and approve drafts.[/dim]")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Processing failed')}")

    console.print()
```

**Step 2: Test manually**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m cli.ivan process --dry-run`
Expected: Shows dry run output

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add cli/ivan/__init__.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(cli): add ivan process command"
```

---

## Task 7: Modify /done to Execute Actions

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api.py`

**Step 1: Write failing test for action execution**

```python
# backend/tests/test_api.py - add

@pytest.mark.asyncio
async def test_done_executes_action(client, db_session):
    """POST /done should execute action for processor tasks."""
    from app.models import Task, CurrentTask

    # Create processor task with action
    proc_task = Task(
        id="proc-31-abc123",
        source="processor",
        title="Respond to #31",
        status="pending",
        url="https://github.com/markster-exec/project-tracker/issues/31",
        assignee="ivan",
        action={
            "type": "github_comment",
            "issue": 31,
            "repo": "markster-exec/project-tracker",
            "body": "Keep it open.",
        },
        linked_task_id="github:31",
    )
    db_session.add(proc_task)

    # Set as current task
    current = CurrentTask(user_id="ivan", task_id="proc-31-abc123")
    db_session.add(current)
    db_session.commit()

    # Mock GitHub writer
    with patch("app.main.get_writer") as mock_writer:
        mock_gh = Mock()
        mock_gh.comment = AsyncMock(return_value=Mock(success=True, message="Comment added"))
        mock_writer.return_value = mock_gh

        response = client.post("/done")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "action executed" in data["message"].lower() or "comment" in data["message"].lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_api.py::test_done_executes_action -v`
Expected: FAIL

**Step 3: Modify /done endpoint to handle actions**

Find the `/done` endpoint in main.py and modify it:

```python
# In the /done endpoint, after getting the current task and before marking it complete:

# Check if task has an action to execute
if current_task.action:
    action = current_task.action
    if action.get("type") == "github_comment":
        # Execute GitHub comment action
        writer = get_writer("github")
        result = await writer.comment(
            source_id=str(action.get("issue")),
            text=action.get("body", ""),
        )
        if not result.success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to post comment: {result.message}",
            )
        logger.info(f"Action executed: posted comment to issue #{action.get('issue')}")

# Then continue with existing completion logic...
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/test_api.py::test_done_executes_action -v`
Expected: PASS

**Step 5: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/main.py backend/tests/test_api.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(api): execute action on /done for processor tasks"
```

---

## Task 8: Modify ivan next to Show Draft

**Files:**
- Modify: `cli/ivan/__init__.py`

**Step 1: Modify format_task to show action draft**

```python
# cli/ivan/__init__.py - modify format_task function (around line 99)

def format_task(task: dict, show_context: bool = True) -> Panel:
    """Format a task as a rich Panel."""
    breakdown = task.get("score_breakdown", {})
    flags = []

    if task.get("is_revenue"):
        flags.append("[green]Revenue[/green]")
    if task.get("is_blocking"):
        flags.append(f"[yellow]Blocking: {', '.join(task['is_blocking'])}[/yellow]")
    flags.append(f"[blue]{breakdown.get('urgency_label', 'Unknown')}[/blue]")

    content = Text()
    content.append(f"Score: {task.get('score', 0)}", style="bold")
    content.append(f" | {' | '.join(flags)}\n", style="dim")

    # Entity context
    if breakdown.get("entity_name"):
        ws_info = ""
        if breakdown.get("workstream_name"):
            ws_info = f" - {breakdown['workstream_name']}"
            if breakdown.get("workstream_deadline"):
                ws_info += f" by {breakdown['workstream_deadline']}"
        content.append(f"→ {breakdown['entity_name']}{ws_info}\n", style="magenta")

    content.append("\n")

    # Show action draft for processor tasks
    action = task.get("action")
    if action and action.get("type") == "github_comment":
        content.append("Draft response:\n", style="bold yellow")
        content.append("┌" + "─" * 50 + "┐\n", style="dim")
        # Word wrap the draft
        draft = action.get("body", "")
        for line in draft.split("\n"):
            while len(line) > 48:
                content.append(f"│ {line[:48]} │\n", style="dim")
                line = line[48:]
            content.append(f"│ {line.ljust(48)} │\n", style="dim")
        content.append("└" + "─" * 50 + "┘\n", style="dim")
        content.append("\n")
        content.append(f"On done: Posts comment to GitHub #{action.get('issue')}\n", style="cyan")
    else:
        # Task URL
        content.append(f"Task: {task.get('url', 'No URL')}", style="cyan underline")

    return Panel(
        content,
        title=f"[bold]{task.get('title', 'Untitled')}[/bold]",
        subtitle=f"[dim]{task.get('source', 'unknown')}:{task.get('id', '?').split(':')[-1]}[/dim]",
        border_style="yellow" if task.get("source") == "processor" else ("green" if task.get("is_revenue") else "blue"),
    )
```

**Step 2: Modify next command to show processor task hints**

```python
# cli/ivan/__init__.py - modify the next command (around line 158-160)

# Replace the hint line at the end:
    if task.get("source") == "processor":
        console.print(
            "[dim][bold]ivan done[/bold] post as-is | [bold]ivan done -e[/bold] edit first | [bold]ivan skip[/bold] next task[/dim]"
        )
    else:
        console.print(
            "[dim]When done: [bold]ivan done[/bold] | To skip: [bold]ivan skip[/bold][/dim]"
        )
```

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add cli/ivan/__init__.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(cli): show draft and action hints for processor tasks"
```

---

## Task 9: Add ivan done -e (Edit Before Posting)

**Files:**
- Modify: `cli/ivan/__init__.py`
- Modify: `backend/app/main.py`

**Step 1: Add edit flag to done command**

```python
# cli/ivan/__init__.py - modify done command

@cli.command()
@click.option("--comment", "-c", help="Add a completion comment")
@click.option("--edit", "-e", is_flag=True, help="Edit action before executing (for processor tasks)")
def done(comment: Optional[str], edit: bool):
    """Mark current task as complete and show next."""

    # If edit flag, get current task and open editor
    if edit:
        with console.status("[bold blue]Getting current task...", spinner="dots"):
            data = api_get("/next")

        if not data.get("task"):
            console.print("[red]⚠️  No current task[/red]")
            return

        task = data["task"]
        action = task.get("action")

        if not action or action.get("type") != "github_comment":
            console.print("[yellow]⚠️  This task has no editable action. Proceeding with normal done.[/yellow]")
        else:
            # Open editor with draft
            import tempfile
            import subprocess

            draft = action.get("body", "")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(draft)
                temp_path = f.name

            # Open in default editor
            editor = os.environ.get("EDITOR", "vim")
            subprocess.call([editor, temp_path])

            # Read edited content
            with open(temp_path) as f:
                edited = f.read().strip()

            os.unlink(temp_path)

            if edited != draft:
                # Update action with edited content
                with console.status("[bold blue]Updating draft...", spinner="dots"):
                    api_post(f"/tasks/{task['id']}/update-action", {"body": edited})
                console.print("[green]✓[/green] Draft updated")

    # Continue with normal done flow
    with console.status("[bold blue]Marking task complete...", spinner="dots"):
        data = api_post("/done")

    # ... rest of existing done logic
```

**Step 2: Add /tasks/{id}/update-action endpoint**

```python
# backend/app/main.py - add endpoint

class UpdateActionRequest(BaseModel):
    body: str


@app.post("/tasks/{task_id}/update-action")
async def update_task_action(
    task_id: str,
    request: UpdateActionRequest,
    db: Session = Depends(get_db),
):
    """Update the action body for a processor task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not task.action:
        raise HTTPException(status_code=400, detail="Task has no action")

    # Update action body
    action = task.action.copy()
    action["body"] = request.body
    task.action = action
    db.commit()

    return {"success": True, "message": "Action updated"}
```

**Step 3: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add cli/ivan/__init__.py backend/app/main.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(cli): add ivan done -e to edit action before posting"
```

---

## Task 10: Export Pending Tasks for Offline

**Files:**
- Modify: `backend/app/exporter.py`

**Step 1: Add pending export to OfflineExporter**

```python
# backend/app/exporter.py - add method to OfflineExporter class

def _export_pending_tasks(self, output_dir: Path) -> int:
    """Export processor tasks as markdown files for offline review.

    Args:
        output_dir: Output pending directory

    Returns:
        Number of pending tasks exported
    """
    # Query processor tasks
    tasks = (
        self.db.query(Task)
        .filter(Task.source == "processor", Task.status == "pending")
        .all()
    )

    count = 0
    for i, task in enumerate(tasks, 1):
        if not task.action:
            continue

        # Build markdown content
        action = task.action
        issue_num = action.get("issue", "?")

        content = f"""---
task_id: {task.id}
github_issue: {issue_num}
repo: {action.get('repo', 'markster-exec/project-tracker')}
action_type: {action.get('type', 'unknown')}
status: {task.status}
linked_task: {task.linked_task_id or ''}
---

# {task.title}

## Context

**URL:** {task.url}
**Linked Task:** {task.linked_task_id or 'None'}

## Description

{task.description or 'No description'}

## Draft Response

{action.get('body', '')}

## Decision

- [ ] approve
- [ ] approve with edits (modify draft above)
- [ ] reject
- [ ] convert to manual task
"""

        filename = f"{i:03d}-respond-{issue_num}.md"
        (output_dir / filename).write_text(content)
        count += 1

    return count
```

**Step 2: Modify export method to include pending**

```python
# backend/app/exporter.py - modify export method

def export(
    self,
    output_path: Path,
    entities_dir: Optional[Path] = None,
    include_briefs: bool = True,
) -> ExportResult:
    """Export tasks and entities to a bundle directory."""
    try:
        output_path = Path(output_path)

        # Create output directory structure
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "entities").mkdir(exist_ok=True)
        (output_path / "pending").mkdir(exist_ok=True)  # NEW
        if include_briefs:
            (output_path / "briefs").mkdir(exist_ok=True)
        (output_path / "outbox").mkdir(exist_ok=True)  # NEW - for decisions

        # Export tasks to SQLite
        tasks_count = self._export_tasks(output_path / "tasks.db")

        # Copy entity files
        entities_count = self._copy_entities(output_path / "entities", entities_dir)

        # Export pending processor tasks  # NEW
        pending_count = self._export_pending_tasks(output_path / "pending")

        # Create manifest
        self._create_manifest(output_path, tasks_count, entities_count, pending_count)

        message = f"Exported {tasks_count} tasks, {entities_count} entities, {pending_count} pending"
        logger.info(message)

        return ExportResult(
            success=True,
            message=message,
            tasks_count=tasks_count,
            entities_count=entities_count,
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return ExportResult(
            success=False,
            message=f"Export failed: {e}",
            tasks_count=0,
            entities_count=0,
        )
```

**Step 3: Update manifest to include pending**

```python
# Update _create_manifest signature and content
def _create_manifest(
    self, output_path: Path, tasks_count: int, entities_count: int, pending_count: int = 0
) -> None:
    """Create MANIFEST.md with export metadata."""
    manifest = f"""# Export Manifest

Exported at: {datetime.utcnow().isoformat()}Z

## Summary

- Tasks: {tasks_count}
- Entities: {entities_count}
- Pending reviews: {pending_count}

## Contents

- `tasks.db` - SQLite database with active tasks
- `entities/` - Entity YAML files
- `pending/` - Processor tasks for offline review
- `outbox/` - Place decisions here for import
- `briefs/` - Brief documents (future use)

## Offline Workflow

1. Review files in `pending/`
2. Mark decisions (approve/reject/edit)
3. Place `decisions.json` in `outbox/`
4. Run `ivan import` when back online
"""
    (output_path / "MANIFEST.md").write_text(manifest)
```

**Step 4: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/exporter.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(export): add pending processor tasks for offline review"
```

---

## Task 11: Import Decisions from Offline

**Files:**
- Create: `backend/app/importer.py`
- Modify: `backend/app/main.py`
- Modify: `cli/ivan/__init__.py`

**Step 1: Create importer module**

```python
# backend/app/importer.py

"""Import decisions from offline review."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .models import Task

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    message: str
    approved: int
    rejected: int
    edited: int


class OfflineImporter:
    """Import decisions from offline bundle."""

    def __init__(self, db_session: Session):
        self.db = db_session

    def import_decisions(self, bundle_path: Path) -> ImportResult:
        """Import decisions from outbox/decisions.json.

        Args:
            bundle_path: Path to the export bundle

        Returns:
            ImportResult with counts
        """
        decisions_file = bundle_path / "outbox" / "decisions.json"

        if not decisions_file.exists():
            return ImportResult(
                success=False,
                message="No decisions.json found in outbox/",
                approved=0,
                rejected=0,
                edited=0,
            )

        try:
            with open(decisions_file) as f:
                decisions = json.load(f)
        except json.JSONDecodeError as e:
            return ImportResult(
                success=False,
                message=f"Invalid JSON in decisions.json: {e}",
                approved=0,
                rejected=0,
                edited=0,
            )

        approved = 0
        rejected = 0
        edited = 0

        for decision in decisions:
            task_id = decision.get("task_id")
            decision_type = decision.get("decision")

            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found, skipping")
                continue

            if decision_type == "approve":
                # Keep task as-is, ready for posting
                approved += 1

            elif decision_type == "approve_edited":
                # Update action body with edited content
                if task.action and decision.get("edited_body"):
                    action = task.action.copy()
                    action["body"] = decision["edited_body"]
                    task.action = action
                    edited += 1

            elif decision_type == "reject":
                # Mark task as rejected/skipped
                task.status = "rejected"
                rejected += 1

        self.db.commit()

        return ImportResult(
            success=True,
            message=f"Imported {len(decisions)} decisions",
            approved=approved,
            rejected=rejected,
            edited=edited,
        )
```

**Step 2: Add /import endpoint**

```python
# backend/app/main.py - add

from .importer import OfflineImporter

class ImportRequest(BaseModel):
    bundle_path: str


class ImportResponse(BaseModel):
    success: bool
    message: str
    approved: int
    rejected: int
    edited: int


@app.post("/import", response_model=ImportResponse)
async def import_decisions(request: ImportRequest, db: Session = Depends(get_db)):
    """Import decisions from offline bundle."""
    importer = OfflineImporter(db)
    result = importer.import_decisions(Path(request.bundle_path))

    return ImportResponse(
        success=result.success,
        message=result.message,
        approved=result.approved,
        rejected=result.rejected,
        edited=result.edited,
    )
```

**Step 3: Add ivan import command**

```python
# cli/ivan/__init__.py - add after export command

@cli.command(name="import")
@click.argument("path", default="~/Developer/Personal/ivan-os/data/sync")
def import_decisions(path: str):
    """Import decisions from offline bundle."""
    import os
    bundle_path = os.path.expanduser(path)

    with console.status("[bold blue]Importing decisions...", spinner="dots"):
        result = api_post("/import", {"bundle_path": bundle_path})

    console.print()
    if result.get("success"):
        console.print("[green]✓[/green] Import complete")
        console.print(f"  Approved: {result.get('approved', 0)}")
        console.print(f"  Edited: {result.get('edited', 0)}")
        console.print(f"  Rejected: {result.get('rejected', 0)}")
        console.print()
        console.print("[dim]Run [bold]ivan next[/bold] to review and post.[/dim]")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Import failed')}")
    console.print()
```

**Step 4: Commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add backend/app/importer.py backend/app/main.py cli/ivan/__init__.py
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "feat(import): add offline decision import"
```

---

## Task 12: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && pytest backend/tests/ -v`
Expected: All tests pass

**Step 2: Fix any failures**

If failures, debug and fix.

**Step 3: Final commit**

```bash
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager add -A
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager commit -m "test: ensure all tests pass for ticket processor"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add action field to Task model | models.py |
| 2 | Create processor - question detection | processor.py |
| 3 | Add draft response generation | processor.py |
| 4 | Process single ticket | processor.py |
| 5 | Add /process endpoint | main.py |
| 6 | Add ivan process CLI | cli/__init__.py |
| 7 | Modify /done to execute actions | main.py |
| 8 | Show draft in ivan next | cli/__init__.py |
| 9 | Add ivan done -e (edit) | cli/__init__.py, main.py |
| 10 | Export pending for offline | exporter.py |
| 11 | Import decisions | importer.py, main.py, cli |
| 12 | Run full test suite | tests/ |

**Total estimated tasks:** 12 bite-sized implementation tasks
