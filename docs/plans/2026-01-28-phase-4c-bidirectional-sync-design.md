---
id: phase-4c-bidirectional-sync-design
title: Phase 4C - Bidirectional Sync Design
type: project
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [phase-4, bidirectional-sync, design, writers, webhooks]
---

# Phase 4C: Bidirectional Sync Design

## Overview

Enable write-back to ClickUp and GitHub: complete tasks, add comments, create tasks. Real-time updates via webhooks.

**Goal:** Tasks can be managed entirely from Slack/CLI without switching to source systems.

## Architecture

### Approach: Unified Writer Interface

Mirrors the existing reader pattern (`ClickUpSyncer`, `GitHubSyncer`). Writers implement a common interface, router dispatches based on `task.source`.

```
SourceWriter (abstract)
├── ClickUpWriter
└── GitHubWriter

Each implements: complete(), comment(), create()
```

### Webhooks: Polling Fallback + Real-time

- Webhooks provide real-time updates from source systems
- Existing hourly sync catches anything webhooks miss
- No single point of failure

## Components

### 1. Writer Interface

```python
# backend/app/writers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WriteResult:
    success: bool
    message: str
    source_id: str | None = None  # For create operations
    conflict: bool = False        # State mismatch detected
    current_state: str | None = None  # Actual state in source

class SourceWriter(ABC):
    """Abstract base for writing to task sources."""

    @abstractmethod
    async def complete(self, source_id: str) -> WriteResult:
        """Mark task complete in source system."""
        pass

    @abstractmethod
    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to task in source system."""
        pass

    @abstractmethod
    async def create(self, title: str, description: str | None = None,
                     entity_id: str | None = None, **kwargs) -> WriteResult:
        """Create new task in source system."""
        pass
```

**Router:**
```python
# backend/app/writers/__init__.py
from typing import Literal

def get_writer(source: Literal["clickup", "github"]) -> SourceWriter:
    if source == "clickup":
        return ClickUpWriter()
    elif source == "github":
        return GitHubWriter()
    raise ValueError(f"Unknown source: {source}")
```

### 2. ClickUp Writer

```python
# backend/app/writers/clickup.py
import httpx
from .base import SourceWriter, WriteResult
from ..config import get_settings

settings = get_settings()

class ClickUpWriter(SourceWriter):
    API_BASE = "https://api.clickup.com/api/v2"

    def __init__(self):
        self.token = settings.clickup_api_token
        self.list_id = settings.clickup_list_id
        self.complete_status = settings.clickup_complete_status or "complete"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Authorization": self.token},
                timeout=30.0
            )
        return self._client

    async def complete(self, source_id: str) -> WriteResult:
        try:
            client = await self._get_client()

            # Check current state (conflict detection)
            get_resp = await client.get(f"{self.API_BASE}/task/{source_id}")
            get_resp.raise_for_status()
            current_status = get_resp.json().get("status", {}).get("status", "").lower()

            if current_status in ["complete", "closed", "done"]:
                return WriteResult(
                    success=True,
                    message="Task already complete",
                    conflict=True,
                    current_state=current_status
                )

            # Update status
            response = await client.put(
                f"{self.API_BASE}/task/{source_id}",
                json={"status": self.complete_status}
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Task completed in ClickUp")
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"ClickUp error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/task/{source_id}/comment",
                json={"comment_text": text}
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Comment added to ClickUp")
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"ClickUp error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def create(self, title: str, description: str | None = None,
                     entity_id: str | None = None, **kwargs) -> WriteResult:
        try:
            payload = {"name": title, "description": description or ""}

            if entity_id:
                payload["tags"] = [f"client:{entity_id}"]

            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/list/{self.list_id}/task",
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return WriteResult(
                success=True,
                message="Task created in ClickUp",
                source_id=data["id"]
            )
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"ClickUp error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")
```

### 3. GitHub Writer

```python
# backend/app/writers/github.py
import httpx
from .base import SourceWriter, WriteResult
from ..config import get_settings

settings = get_settings()

class GitHubWriter(SourceWriter):
    API_BASE = "https://api.github.com"

    def __init__(self):
        self.token = settings.github_token
        self.repo = settings.github_repo
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=30.0
            )
        return self._client

    async def complete(self, source_id: str) -> WriteResult:
        try:
            client = await self._get_client()

            # Check current state (conflict detection)
            get_resp = await client.get(
                f"{self.API_BASE}/repos/{self.repo}/issues/{source_id}"
            )
            get_resp.raise_for_status()
            current = get_resp.json()

            if current["state"] == "closed":
                return WriteResult(
                    success=True,
                    message="Issue already closed",
                    conflict=True,
                    current_state="closed"
                )

            # Close issue
            response = await client.patch(
                f"{self.API_BASE}/repos/{self.repo}/issues/{source_id}",
                json={"state": "closed"}
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Issue closed in GitHub")
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"GitHub error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/repos/{self.repo}/issues/{source_id}/comments",
                json={"body": text}
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Comment added to GitHub")
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"GitHub error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def create(self, title: str, description: str | None = None,
                     entity_id: str | None = None, **kwargs) -> WriteResult:
        try:
            # Prepend entity tag to title
            if entity_id:
                title = f"[CLIENT:{entity_id}] {title}"

            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/repos/{self.repo}/issues",
                json={"title": title, "body": description or ""}
            )
            response.raise_for_status()
            data = response.json()

            return WriteResult(
                success=True,
                message="Issue created in GitHub",
                source_id=str(data["number"])
            )
        except httpx.HTTPStatusError as e:
            return WriteResult(success=False, message=f"GitHub error: {e.response.status_code}")
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")
```

### 4. Write API Endpoints

```python
# backend/app/main.py (additions)
from typing import Literal
from .writers import get_writer

class CommentRequest(BaseModel):
    text: str

class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
    source: Literal["clickup", "github"] = "clickup"
    entity_id: str | None = None

class ActionResponse(BaseModel):
    success: bool
    message: str
    completed_task_id: str | None = None  # Added for comment-after-done
    next_task: Optional[TaskResponse] = None


@app.post("/tasks/{task_id}/complete", response_model=ActionResponse)
async def complete_task(task_id: str, db: Session = Depends(get_db)):
    """Mark task complete in source system."""
    # Validate task_id format
    if ":" not in task_id:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    source, source_id = task_id.split(":", 1)

    writer = get_writer(task.source)
    result = await writer.complete(source_id)

    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)

    # Update local state
    task.status = "done"
    task.updated_at = datetime.utcnow()
    db.commit()

    # Build message
    message = result.message
    if result.conflict:
        message = f"Note: {result.message} (completed externally)"

    # Get next task (existing logic)
    next_task_response = None
    # ... (reuse existing next task logic from /done endpoint)

    return ActionResponse(
        success=True,
        message=message,
        completed_task_id=task_id,
        next_task=next_task_response
    )


@app.post("/tasks/{task_id}/comment", response_model=ActionResponse)
async def add_comment(task_id: str, request: CommentRequest, db: Session = Depends(get_db)):
    """Add comment to task in source system."""
    if ":" not in task_id:
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    source, source_id = task_id.split(":", 1)
    writer = get_writer(task.source)
    result = await writer.comment(source_id, request.text)

    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)

    return ActionResponse(success=True, message=result.message)


@app.post("/tasks", response_model=ActionResponse)
async def create_task(request: CreateTaskRequest, db: Session = Depends(get_db)):
    """Create task in source system."""
    writer = get_writer(request.source)
    result = await writer.create(
        title=request.title,
        description=request.description,
        entity_id=request.entity_id
    )

    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)

    # Sync to pull new task into local DB
    await sync_all_sources()

    return ActionResponse(
        success=True,
        message=f"{result.message} (ID: {result.source_id})"
    )
```

### 5. Webhook Receivers

```python
# backend/app/webhooks.py
import hmac
import hashlib
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Task, get_db

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/clickup")
async def clickup_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle ClickUp webhook events."""
    body = await request.body()

    # Verify signature
    if settings.clickup_webhook_secret:
        signature = request.headers.get("X-ClickUp-Signature", "")
        expected = hmac.new(
            settings.clickup_webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event = payload.get("event")
    task_data = payload.get("task", {})
    task_id = task_data.get("id")

    if not task_id:
        return {"status": "ignored", "reason": "no task_id"}

    local_id = f"clickup:{task_id}"
    task = db.query(Task).filter(Task.id == local_id).first()

    if not task:
        logger.info(f"Webhook for unknown task: {local_id}")
        return {"status": "ignored", "reason": "task not tracked"}

    if event == "taskStatusUpdated":
        new_status = task_data.get("status", {}).get("status", "").lower()
        if new_status in ["complete", "closed", "done"]:
            task.status = "done"
        elif new_status in ["in progress", "in_progress"]:
            task.status = "in_progress"
        else:
            task.status = "todo"
        task.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Task {local_id} status updated to {task.status}")

    elif event == "taskCommentPosted":
        task.last_activity = datetime.utcnow()
        task.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"Task {local_id} received comment")

    return {"status": "processed", "event": event}


@router.post("/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub webhook events."""
    body = await request.body()

    # Verify signature
    if settings.github_webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.github_webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event")

    if event_type == "issues":
        action = payload.get("action")
        issue = payload.get("issue", {})
        issue_number = issue.get("number")

        if not issue_number:
            return {"status": "ignored", "reason": "no issue number"}

        local_id = f"github:{issue_number}"
        task = db.query(Task).filter(Task.id == local_id).first()

        if not task:
            return {"status": "ignored", "reason": "task not tracked"}

        if action == "closed":
            task.status = "done"
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Issue {local_id} closed externally")

        elif action == "reopened":
            task.status = "todo"
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Issue {local_id} reopened externally")

    elif event_type == "issue_comment":
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        local_id = f"github:{issue_number}"
        task = db.query(Task).filter(Task.id == local_id).first()

        if task:
            task.last_activity = datetime.utcnow()
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"Issue {local_id} received comment")

    return {"status": "processed", "event": event_type}
```

**Register in main.py:**
```python
from .webhooks import router as webhooks_router
app.include_router(webhooks_router)
```

### 6. Conflict Resolution Strategy

**Principle: Last-write-wins with notification**

- Check current state before writing
- If already in target state, return `success=True` with `conflict=True`
- Source system is authoritative
- Inform user of conflicts, don't fail

**Implementation:** Built into writers (see sections 2-3).

### 7. CLI Commands

```python
# cli/ivan/__init__.py (additions)

@cli.command()
@click.option("--comment", "-c", help="Add comment when completing")
def done(comment: str | None):
    """Mark current task as done in source system."""
    response = requests.post(f"{API_URL}/done")
    data = response.json()

    click.echo(f"✓ {data['message']}")

    if comment and data.get("completed_task_id"):
        requests.post(
            f"{API_URL}/tasks/{data['completed_task_id']}/comment",
            json={"text": comment}
        )
        click.echo(f"  Comment added")

    if data.get("next_task"):
        click.echo(f"Next: {data['next_task']['title']}")


@cli.command()
@click.argument("text")
def comment(text: str):
    """Add comment to current task."""
    current = requests.get(f"{API_URL}/current").json()
    if not current.get("task_id"):
        click.echo("No current task", err=True)
        return

    response = requests.post(
        f"{API_URL}/tasks/{current['task_id']}/comment",
        json={"text": text}
    )
    if response.ok:
        click.echo(f"✓ Comment added to current task")
    else:
        click.echo(f"✗ {response.json().get('detail', 'Failed')}", err=True)


@cli.command()
@click.argument("title")
@click.option("--source", "-s", type=click.Choice(["clickup", "github"]), default="clickup")
@click.option("--entity", "-e", help="Entity ID to tag")
@click.option("--description", "-d", help="Task description")
def create(title: str, source: str, entity: str | None, description: str | None):
    """Create new task in source system."""
    response = requests.post(
        f"{API_URL}/tasks",
        json={
            "title": title,
            "source": source,
            "entity_id": entity,
            "description": description
        }
    )
    if response.ok:
        click.echo(f"✓ {response.json()['message']}")
    else:
        click.echo(f"✗ {response.json().get('detail', 'Failed')}", err=True)
```

### 8. Slack Bot Commands

Add to `handle_message()` in `backend/app/bot.py`:

| Command | Action |
|---------|--------|
| `done` | Complete current task in source |
| `comment <text>` | Add comment to current task |
| `create <title>` | Create task in ClickUp (default) |

## Configuration Additions

Add to `backend/app/config.py`:

```python
class Settings(BaseSettings):
    # Existing...

    # Writer config
    clickup_complete_status: str = "complete"

    # Webhook secrets
    clickup_webhook_secret: str | None = None
    github_webhook_secret: str | None = None
```

## File Structure

```
backend/app/
├── writers/
│   ├── __init__.py      # get_writer() router
│   ├── base.py          # SourceWriter ABC, WriteResult
│   ├── clickup.py       # ClickUpWriter
│   └── github.py        # GitHubWriter
├── webhooks.py          # Webhook receivers
├── main.py              # Updated with write endpoints
└── config.py            # Updated with new settings

cli/ivan/
└── __init__.py          # Updated with done, comment, create commands
```

## Implementation Order

1. **Writers** - base.py, clickup.py, github.py
2. **Config** - Add new settings
3. **API** - Write endpoints in main.py
4. **Webhooks** - webhooks.py + registration
5. **CLI** - Update cli/ivan/__init__.py
6. **Bot** - Update bot.py with commands
7. **Tests** - Writer tests, endpoint tests, webhook tests
8. **Docs** - Webhook setup instructions

## Acceptance Criteria

- [ ] `ivan done` marks task complete in source system (ClickUp or GitHub)
- [ ] "done" in Slack marks current task complete in source
- [ ] `ivan comment "notes"` adds comment to current task in source
- [ ] `ivan create "title"` creates task in ClickUp
- [ ] `ivan create "title" -s github` creates issue in GitHub
- [ ] External task completion syncs within seconds via webhook
- [ ] Conflict: external change detected, user notified, operation succeeds

---

*Design approved: 2026-01-28*
