---
id: phase-4c-implementation-plan
title: Phase 4C - Bidirectional Sync Implementation Plan
type: project
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [phase-4, bidirectional-sync, implementation, plan]
---

# Phase 4C: Bidirectional Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable write-back to ClickUp and GitHub (complete tasks, add comments, create tasks) with real-time webhook updates.

**Architecture:** Unified writer interface (`SourceWriter` ABC) with `ClickUpWriter` and `GitHubWriter` implementations. Webhooks provide real-time updates; hourly sync catches missed events.

**Tech Stack:** Python 3.11+, FastAPI, httpx, pydantic, pytest, SQLAlchemy

**Design Doc:** `docs/plans/2026-01-28-phase-4c-bidirectional-sync-design.md`

---

## Task 1: Writer Base Classes

**Files:**
- Create: `backend/app/writers/__init__.py`
- Create: `backend/app/writers/base.py`
- Test: `backend/tests/test_writers.py`

**Step 1: Create writers package init**

```python
# backend/app/writers/__init__.py
"""Writers for updating tasks in source systems."""

from typing import Literal

from .base import SourceWriter, WriteResult
from .clickup import ClickUpWriter
from .github import GitHubWriter

__all__ = ["SourceWriter", "WriteResult", "get_writer", "ClickUpWriter", "GitHubWriter"]


def get_writer(source: Literal["clickup", "github"]) -> SourceWriter:
    """Get the appropriate writer for a source.

    Args:
        source: The task source ("clickup" or "github")

    Returns:
        SourceWriter implementation for the source

    Raises:
        ValueError: If source is unknown
    """
    if source == "clickup":
        return ClickUpWriter()
    elif source == "github":
        return GitHubWriter()
    raise ValueError(f"Unknown source: {source}")
```

**Step 2: Create base writer classes**

```python
# backend/app/writers/base.py
"""Base classes for source writers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class WriteResult:
    """Result of a write operation to a source system.

    Attributes:
        success: Whether the operation completed successfully
        message: Human-readable result message
        source_id: ID in source system (for create operations)
        conflict: Whether a state conflict was detected
        current_state: Actual state in source system (if conflict)
    """

    success: bool
    message: str
    source_id: str | None = None
    conflict: bool = False
    current_state: str | None = None


class SourceWriter(ABC):
    """Abstract base class for writing to task sources."""

    @abstractmethod
    async def complete(self, source_id: str) -> WriteResult:
        """Mark task complete in source system.

        Args:
            source_id: The task ID in the source system

        Returns:
            WriteResult indicating success/failure
        """
        pass

    @abstractmethod
    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to task in source system.

        Args:
            source_id: The task ID in the source system
            text: Comment text to add

        Returns:
            WriteResult indicating success/failure
        """
        pass

    @abstractmethod
    async def create(
        self,
        title: str,
        description: str | None = None,
        entity_id: str | None = None,
        **kwargs,
    ) -> WriteResult:
        """Create new task in source system.

        Args:
            title: Task title
            description: Task description (optional)
            entity_id: Entity ID for tagging (optional)
            **kwargs: Additional source-specific options

        Returns:
            WriteResult with source_id of created task
        """
        pass
```

**Step 3: Create test file with basic tests**

```python
# backend/tests/test_writers.py
"""Tests for source writers."""

import pytest
from app.writers.base import WriteResult, SourceWriter


class TestWriteResult:
    """Test WriteResult dataclass."""

    def test_success_result(self):
        """WriteResult with success=True."""
        result = WriteResult(success=True, message="Done")
        assert result.success is True
        assert result.message == "Done"
        assert result.source_id is None
        assert result.conflict is False

    def test_failure_result(self):
        """WriteResult with success=False."""
        result = WriteResult(success=False, message="Failed")
        assert result.success is False
        assert result.message == "Failed"

    def test_conflict_result(self):
        """WriteResult with conflict detected."""
        result = WriteResult(
            success=True,
            message="Already done",
            conflict=True,
            current_state="closed",
        )
        assert result.success is True
        assert result.conflict is True
        assert result.current_state == "closed"

    def test_create_result_with_source_id(self):
        """WriteResult from create includes source_id."""
        result = WriteResult(
            success=True,
            message="Created",
            source_id="abc123",
        )
        assert result.source_id == "abc123"
```

**Step 4: Run tests to verify base classes**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add backend/app/writers/ backend/tests/test_writers.py
git commit -m "feat(writers): add base SourceWriter and WriteResult classes"
```

---

## Task 2: Config Settings for Writers

**Files:**
- Modify: `backend/app/config.py:7-48`

**Step 1: Add writer settings to config**

Add these fields to the `Settings` class in `backend/app/config.py` after line 31 (after `slack_ivan_user_id`):

```python
    # Writer settings
    clickup_complete_status: str = "complete"

    # Webhook secrets (for signature verification)
    clickup_webhook_secret: str = ""
    github_webhook_secret: str = ""
```

**Step 2: Run existing tests to verify no breakage**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/ -v --ignore=backend/tests/test_writers.py`
Expected: All existing tests PASS

**Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(config): add writer and webhook settings"
```

---

## Task 3: ClickUp Writer

**Files:**
- Create: `backend/app/writers/clickup.py`
- Modify: `backend/tests/test_writers.py`

**Step 1: Write failing test for ClickUp complete**

Add to `backend/tests/test_writers.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


class TestClickUpWriter:
    """Test ClickUpWriter."""

    @pytest.fixture
    def writer(self):
        """Create ClickUpWriter with mocked settings."""
        with patch("app.writers.clickup.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                clickup_api_token="test-token",
                clickup_list_id="test-list",
                clickup_complete_status="complete",
            )
            from app.writers.clickup import ClickUpWriter

            return ClickUpWriter()

    @pytest.mark.asyncio
    async def test_complete_success(self, writer):
        """Complete marks task as complete in ClickUp."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": {"status": "to do"}}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            client.put.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is True
            assert "ClickUp" in result.message
            client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_already_done(self, writer):
        """Complete detects already-completed task."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": {"status": "complete"}}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is True
            assert result.conflict is True
            client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_http_error(self, writer):
        """Complete handles HTTP errors gracefully."""
        with patch.object(writer, "_get_client") as mock_client:
            client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 404
            client.get.side_effect = httpx.HTTPStatusError(
                "Not found", request=MagicMock(), response=error_response
            )
            mock_client.return_value = client

            result = await writer.complete("abc123")

            assert result.success is False
            assert "404" in result.message
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py::TestClickUpWriter -v`
Expected: FAIL with "No module named 'app.writers.clickup'"

**Step 3: Implement ClickUp writer**

```python
# backend/app/writers/clickup.py
"""ClickUp writer for updating tasks."""

import httpx

from ..config import get_settings
from .base import SourceWriter, WriteResult


class ClickUpWriter(SourceWriter):
    """Writer for ClickUp tasks."""

    API_BASE = "https://api.clickup.com/api/v2"

    def __init__(self):
        settings = get_settings()
        self.token = settings.clickup_api_token
        self.list_id = settings.clickup_list_id
        self.complete_status = settings.clickup_complete_status
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"Authorization": self.token},
                timeout=30.0,
            )
        return self._client

    async def complete(self, source_id: str) -> WriteResult:
        """Mark task complete in ClickUp."""
        try:
            client = await self._get_client()

            # Check current state (conflict detection)
            get_resp = await client.get(f"{self.API_BASE}/task/{source_id}")
            get_resp.raise_for_status()
            current_status = (
                get_resp.json().get("status", {}).get("status", "").lower()
            )

            if current_status in ["complete", "closed", "done"]:
                return WriteResult(
                    success=True,
                    message="Task already complete in ClickUp",
                    conflict=True,
                    current_state=current_status,
                )

            # Update status
            response = await client.put(
                f"{self.API_BASE}/task/{source_id}",
                json={"status": self.complete_status},
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Task completed in ClickUp")

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"ClickUp error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to task in ClickUp."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/task/{source_id}/comment",
                json={"comment_text": text},
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Comment added to ClickUp")

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"ClickUp error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def create(
        self,
        title: str,
        description: str | None = None,
        entity_id: str | None = None,
        **kwargs,
    ) -> WriteResult:
        """Create task in ClickUp."""
        try:
            payload = {"name": title, "description": description or ""}

            if entity_id:
                payload["tags"] = [f"client:{entity_id}"]

            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/list/{self.list_id}/task",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return WriteResult(
                success=True,
                message="Task created in ClickUp",
                source_id=data["id"],
            )

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"ClickUp error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py::TestClickUpWriter -v`
Expected: PASS (3 tests)

**Step 5: Add tests for comment and create**

Add to `TestClickUpWriter` class:

```python
    @pytest.mark.asyncio
    async def test_comment_success(self, writer):
        """Comment adds comment to task."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.comment("abc123", "Test comment")

            assert result.success is True
            client.post.assert_called_once()
            call_args = client.post.call_args
            assert "comment" in call_args[0][0]
            assert call_args[1]["json"]["comment_text"] == "Test comment"

    @pytest.mark.asyncio
    async def test_create_success(self, writer):
        """Create creates task in ClickUp."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "new-task-id"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Task", description="Test desc")

            assert result.success is True
            assert result.source_id == "new-task-id"

    @pytest.mark.asyncio
    async def test_create_with_entity_tag(self, writer):
        """Create adds entity tag when entity_id provided."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"id": "new-task-id"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Task", entity_id="mark-smith")

            assert result.success is True
            call_args = client.post.call_args
            assert call_args[1]["json"]["tags"] == ["client:mark-smith"]
```

**Step 6: Run all writer tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py -v`
Expected: PASS (all tests)

**Step 7: Commit**

```bash
git add backend/app/writers/clickup.py backend/tests/test_writers.py
git commit -m "feat(writers): add ClickUpWriter implementation"
```

---

## Task 4: GitHub Writer

**Files:**
- Create: `backend/app/writers/github.py`
- Modify: `backend/tests/test_writers.py`

**Step 1: Write failing test for GitHub complete**

Add to `backend/tests/test_writers.py`:

```python
class TestGitHubWriter:
    """Test GitHubWriter."""

    @pytest.fixture
    def writer(self):
        """Create GitHubWriter with mocked settings."""
        with patch("app.writers.github.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                github_token="test-token",
                github_repo="owner/repo",
            )
            from app.writers.github import GitHubWriter

            return GitHubWriter()

    @pytest.mark.asyncio
    async def test_complete_success(self, writer):
        """Complete closes issue in GitHub."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_get_response = MagicMock()
            mock_get_response.json.return_value = {"state": "open"}
            mock_get_response.raise_for_status = MagicMock()

            mock_patch_response = MagicMock()
            mock_patch_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_get_response
            client.patch.return_value = mock_patch_response
            mock_client.return_value = client

            result = await writer.complete("42")

            assert result.success is True
            assert "GitHub" in result.message
            client.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_already_closed(self, writer):
        """Complete detects already-closed issue."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"state": "closed"}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.get.return_value = mock_response
            mock_client.return_value = client

            result = await writer.complete("42")

            assert result.success is True
            assert result.conflict is True
            client.patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_comment_success(self, writer):
        """Comment adds comment to issue."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.comment("42", "Test comment")

            assert result.success is True
            client.post.assert_called_once()
            call_args = client.post.call_args
            assert "/comments" in call_args[0][0]
            assert call_args[1]["json"]["body"] == "Test comment"

    @pytest.mark.asyncio
    async def test_create_success(self, writer):
        """Create creates issue in GitHub."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"number": 99}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Issue", description="Test body")

            assert result.success is True
            assert result.source_id == "99"

    @pytest.mark.asyncio
    async def test_create_with_entity_tag(self, writer):
        """Create prepends entity tag to title."""
        with patch.object(writer, "_get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {"number": 99}
            mock_response.raise_for_status = MagicMock()

            client = AsyncMock()
            client.post.return_value = mock_response
            mock_client.return_value = client

            result = await writer.create("Test Issue", entity_id="mark-smith")

            assert result.success is True
            call_args = client.post.call_args
            assert call_args[1]["json"]["title"] == "[CLIENT:mark-smith] Test Issue"
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py::TestGitHubWriter -v`
Expected: FAIL with "No module named 'app.writers.github'"

**Step 3: Implement GitHub writer**

```python
# backend/app/writers/github.py
"""GitHub writer for updating issues."""

import httpx

from ..config import get_settings
from .base import SourceWriter, WriteResult


class GitHubWriter(SourceWriter):
    """Writer for GitHub issues."""

    API_BASE = "https://api.github.com"

    def __init__(self):
        settings = get_settings()
        self.token = settings.github_token
        self.repo = settings.github_repo
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=30.0,
            )
        return self._client

    async def complete(self, source_id: str) -> WriteResult:
        """Close issue in GitHub."""
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
                    message="Issue already closed in GitHub",
                    conflict=True,
                    current_state="closed",
                )

            # Close issue
            response = await client.patch(
                f"{self.API_BASE}/repos/{self.repo}/issues/{source_id}",
                json={"state": "closed"},
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Issue closed in GitHub")

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"GitHub error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to issue in GitHub."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/repos/{self.repo}/issues/{source_id}/comments",
                json={"body": text},
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Comment added to GitHub")

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"GitHub error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def create(
        self,
        title: str,
        description: str | None = None,
        entity_id: str | None = None,
        **kwargs,
    ) -> WriteResult:
        """Create issue in GitHub."""
        try:
            # Prepend entity tag to title
            if entity_id:
                title = f"[CLIENT:{entity_id}] {title}"

            client = await self._get_client()
            response = await client.post(
                f"{self.API_BASE}/repos/{self.repo}/issues",
                json={"title": title, "body": description or ""},
            )
            response.raise_for_status()
            data = response.json()

            return WriteResult(
                success=True,
                message="Issue created in GitHub",
                source_id=str(data["number"]),
            )

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"GitHub error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py::TestGitHubWriter -v`
Expected: PASS (6 tests)

**Step 5: Run all writer tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_writers.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add backend/app/writers/github.py backend/tests/test_writers.py
git commit -m "feat(writers): add GitHubWriter implementation"
```

---

## Task 5: Write API Endpoints

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_api.py`

**Step 1: Write failing test for complete endpoint**

Add to `backend/tests/test_api.py`:

```python
from unittest.mock import patch, MagicMock, AsyncMock


class TestCompleteEndpoint:
    """Test /tasks/{task_id}/complete endpoint."""

    def test_complete_invalid_task_id(self, client):
        """Invalid task ID format returns 400."""
        response = client.post("/tasks/invalid/complete")
        assert response.status_code == 400
        assert "Invalid task ID" in response.json()["detail"]

    def test_complete_task_not_found(self, client):
        """Non-existent task returns 404."""
        response = client.post("/tasks/clickup:nonexistent/complete")
        assert response.status_code == 404

    def test_complete_success(self, client):
        """Successful complete updates task and returns success."""
        # Create a task
        db = TestSessionLocal()
        task = Task(
            id="clickup:abc123",
            source="clickup",
            title="Test Task",
            status="todo",
            assignee="ivan",
            url="http://test",
        )
        db.add(task)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = MagicMock()
            mock_writer.complete = AsyncMock(
                return_value=MagicMock(success=True, message="Done", conflict=False)
            )
            mock_get_writer.return_value = mock_writer

            response = client.post("/tasks/clickup:abc123/complete")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["completed_task_id"] == "clickup:abc123"


class TestCommentEndpoint:
    """Test /tasks/{task_id}/comment endpoint."""

    def test_comment_success(self, client):
        """Successful comment returns success."""
        db = TestSessionLocal()
        task = Task(
            id="clickup:abc123",
            source="clickup",
            title="Test Task",
            status="todo",
            assignee="ivan",
            url="http://test",
        )
        db.add(task)
        db.commit()
        db.close()

        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = MagicMock()
            mock_writer.comment = AsyncMock(
                return_value=MagicMock(success=True, message="Comment added")
            )
            mock_get_writer.return_value = mock_writer

            response = client.post(
                "/tasks/clickup:abc123/comment", json={"text": "Test comment"}
            )
            assert response.status_code == 200
            assert response.json()["success"] is True


class TestCreateTaskEndpoint:
    """Test POST /tasks endpoint."""

    def test_create_success(self, client):
        """Successful create returns success."""
        with patch("app.main.get_writer") as mock_get_writer:
            mock_writer = MagicMock()
            mock_writer.create = AsyncMock(
                return_value=MagicMock(
                    success=True, message="Task created", source_id="new123"
                )
            )
            mock_get_writer.return_value = mock_writer

            with patch("app.main.sync_all_sources") as mock_sync:
                mock_sync.return_value = {}

                response = client.post(
                    "/tasks", json={"title": "New Task", "source": "clickup"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "new123" in data["message"]
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_api.py::TestCompleteEndpoint -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Add write endpoints to main.py**

Add imports at top of `backend/app/main.py`:

```python
from typing import Literal
from .writers import get_writer
```

Add Pydantic models after existing models (around line 290):

```python
class CommentRequest(BaseModel):
    text: str


class CreateTaskRequest(BaseModel):
    title: str
    description: str | None = None
    source: Literal["clickup", "github"] = "clickup"
    entity_id: str | None = None
```

Update `ActionResponse` to include `completed_task_id`:

```python
class ActionResponse(BaseModel):
    success: bool
    message: str
    completed_task_id: str | None = None
    next_task: Optional[TaskResponse] = None
```

Add new endpoints after `/sync` endpoint:

```python
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

    return ActionResponse(
        success=True,
        message=message,
        completed_task_id=task_id,
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
        entity_id=request.entity_id,
    )

    if not result.success:
        raise HTTPException(status_code=502, detail=result.message)

    # Sync to pull new task into local DB
    await sync_all_sources()

    return ActionResponse(
        success=True,
        message=f"{result.message} (ID: {result.source_id})",
    )
```

**Step 4: Update test client fixture to include new endpoints**

In `backend/tests/test_api.py`, update the `client` fixture:

```python
@pytest.fixture
def client():
    """Create test client with mocked dependencies."""
    from app.main import (
        health_check,
        get_tasks,
        get_next_task,
        mark_done,
        skip_task,
        force_sync,
        get_morning_briefing,
        list_entities,
        get_entity_detail,
        reload_entities,
        complete_task,
        add_comment,
        create_task,
        get_db,
    )

    test_app = FastAPI()

    # Add routes manually without lifespan to avoid scheduler issues
    test_app.get("/health")(health_check)
    test_app.get("/tasks")(get_tasks)
    test_app.get("/next")(get_next_task)
    test_app.post("/done")(mark_done)
    test_app.post("/skip")(skip_task)
    test_app.post("/sync")(force_sync)
    test_app.get("/morning")(get_morning_briefing)
    test_app.get("/entities")(list_entities)
    test_app.get("/entities/{entity_id}")(get_entity_detail)
    test_app.post("/entities/reload")(reload_entities)
    test_app.post("/tasks/{task_id}/complete")(complete_task)
    test_app.post("/tasks/{task_id}/comment")(add_comment)
    test_app.post("/tasks")(create_task)

    # Override the database dependency
    test_app.dependency_overrides[get_db] = get_test_db

    with TestClient(test_app) as c:
        yield c
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_api.py::TestCompleteEndpoint backend/tests/test_api.py::TestCommentEndpoint backend/tests/test_api.py::TestCreateTaskEndpoint -v`
Expected: PASS (all tests)

**Step 6: Run all API tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_api.py -v`
Expected: PASS (all tests)

**Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/test_api.py
git commit -m "feat(api): add write endpoints for complete, comment, create"
```

---

## Task 6: Webhook Receivers

**Files:**
- Create: `backend/app/webhooks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_webhooks.py`

**Step 1: Write failing test for ClickUp webhook**

```python
# backend/tests/test_webhooks.py
"""Tests for webhook receivers."""

import json
import hmac
import hashlib
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch, MagicMock
from datetime import date

from app.models import Base, Task


# Create test database
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    from app.webhooks import router
    from app.models import get_db

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = get_test_db

    with TestClient(test_app) as c:
        yield c


class TestClickUpWebhook:
    """Test ClickUp webhook receiver."""

    def test_ignores_unknown_task(self, client):
        """Webhook for unknown task is ignored."""
        payload = {"event": "taskStatusUpdated", "task": {"id": "unknown123"}}

        response = client.post("/webhooks/clickup", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_updates_task_status_to_done(self, client):
        """Task status update to complete marks task done."""
        # Create tracked task
        db = TestSessionLocal()
        task = Task(
            id="clickup:abc123",
            source="clickup",
            title="Test Task",
            status="todo",
            assignee="ivan",
            url="http://test",
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {
            "event": "taskStatusUpdated",
            "task": {"id": "abc123", "status": {"status": "complete"}},
        }

        with patch("app.webhooks.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(clickup_webhook_secret="")

            response = client.post("/webhooks/clickup", json=payload)

            assert response.status_code == 200
            assert response.json()["status"] == "processed"

        # Verify task updated
        db = TestSessionLocal()
        task = db.query(Task).filter(Task.id == "clickup:abc123").first()
        assert task.status == "done"
        db.close()


class TestGitHubWebhook:
    """Test GitHub webhook receiver."""

    def test_closes_issue(self, client):
        """Issues.closed event marks task done."""
        db = TestSessionLocal()
        task = Task(
            id="github:42",
            source="github",
            title="Test Issue",
            status="todo",
            assignee="ivan",
            url="http://test",
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {"action": "closed", "issue": {"number": 42}}

        with patch("app.webhooks.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_webhook_secret="")

            response = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "issues"},
            )

            assert response.status_code == 200

        db = TestSessionLocal()
        task = db.query(Task).filter(Task.id == "github:42").first()
        assert task.status == "done"
        db.close()

    def test_reopens_issue(self, client):
        """Issues.reopened event marks task todo."""
        db = TestSessionLocal()
        task = Task(
            id="github:42",
            source="github",
            title="Test Issue",
            status="done",
            assignee="ivan",
            url="http://test",
        )
        db.add(task)
        db.commit()
        db.close()

        payload = {"action": "reopened", "issue": {"number": 42}}

        with patch("app.webhooks.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(github_webhook_secret="")

            response = client.post(
                "/webhooks/github",
                json=payload,
                headers={"X-GitHub-Event": "issues"},
            )

            assert response.status_code == 200

        db = TestSessionLocal()
        task = db.query(Task).filter(Task.id == "github:42").first()
        assert task.status == "todo"
        db.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_webhooks.py -v`
Expected: FAIL with "No module named 'app.webhooks'"

**Step 3: Implement webhook receivers**

```python
# backend/app/webhooks.py
"""Webhook receivers for ClickUp and GitHub."""

import hmac
import hashlib
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Task, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/clickup")
async def clickup_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle ClickUp webhook events."""
    settings = get_settings()
    body = await request.body()

    # Verify signature if secret configured
    if settings.clickup_webhook_secret:
        signature = request.headers.get("X-ClickUp-Signature", "")
        expected = hmac.new(
            settings.clickup_webhook_secret.encode(),
            body,
            hashlib.sha256,
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
    settings = get_settings()
    body = await request.body()

    # Verify signature if secret configured
    if settings.github_webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            settings.github_webhook_secret.encode(),
            body,
            hashlib.sha256,
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

**Step 4: Register webhooks router in main.py**

Add to `backend/app/main.py` after other imports:

```python
from .webhooks import router as webhooks_router
```

Add after `app = FastAPI(...)`:

```python
app.include_router(webhooks_router)
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_webhooks.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add backend/app/webhooks.py backend/app/main.py backend/tests/test_webhooks.py
git commit -m "feat(webhooks): add ClickUp and GitHub webhook receivers"
```

---

## Task 7: CLI Commands

**Files:**
- Modify: `cli/ivan/__init__.py`

**Step 1: Add comment command to CLI**

Add after the `done` command in `cli/ivan/__init__.py`:

```python
@cli.command()
@click.argument("text")
def comment(text: str):
    """Add comment to current task."""
    # Get current task first
    data = api_get("/next")
    if not data.get("task"):
        console.print("[red]No current task to comment on[/red]")
        return

    task_id = data["task"]["id"]

    with console.status("[bold blue]Adding comment...", spinner="dots"):
        result = api_post(f"/tasks/{task_id}/comment", {"text": text})

    if result.get("success"):
        console.print(f"[green]✓[/green] {result.get('message', 'Comment added')}")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Failed to add comment')}")


@cli.command()
@click.argument("title")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["clickup", "github"]),
    default="clickup",
    help="Source system to create task in",
)
@click.option("--entity", "-e", help="Entity ID to tag task with")
@click.option("--description", "-d", help="Task description")
def create(title: str, source: str, entity: str, description: str):
    """Create new task in source system."""
    payload = {
        "title": title,
        "source": source,
    }
    if entity:
        payload["entity_id"] = entity
    if description:
        payload["description"] = description

    with console.status(
        f"[bold blue]Creating task in {source.capitalize()}...", spinner="dots"
    ):
        result = api_post("/tasks", payload)

    if result.get("success"):
        console.print(f"[green]✓[/green] {result.get('message', 'Task created')}")
    else:
        console.print(f"[red]✗[/red] {result.get('message', 'Failed to create task')}")
```

**Step 2: Update done command to write back to source**

Replace the existing `done` command:

```python
@cli.command()
@click.option("--comment", "-c", help="Add comment when completing")
def done(comment: str):
    """Mark current task as complete in source system and show next."""
    # Get current task first
    data = api_get("/next")
    if not data.get("task"):
        console.print("[dim]No current task to complete[/dim]")
        return

    task_id = data["task"]["id"]

    with console.status("[bold blue]Marking task complete...", spinner="dots"):
        result = api_post(f"/tasks/{task_id}/complete")

    if result.get("success"):
        console.print()
        console.print(f"[green]✓[/green] {result.get('message', 'Task completed')}")

        # Add comment if provided
        if comment and result.get("completed_task_id"):
            comment_result = api_post(
                f"/tasks/{result['completed_task_id']}/comment",
                {"text": comment},
            )
            if comment_result.get("success"):
                console.print(f"[green]✓[/green] Comment added")

        # Get next task
        next_data = api_get("/next")
        if next_data.get("task"):
            console.print()
            console.print("[bold]Next up:[/bold]")
            console.print(format_task(next_data["task"]))
        else:
            console.print()
            console.print("[green]✨ All done! No more tasks.[/green]")
        console.print()
    else:
        console.print()
        console.print(
            f"[red]⚠️  {result.get('message', 'Could not complete task')}[/red]"
        )
        console.print("[dim]Tip: Run [bold]ivan next[/bold] first to get a task.[/dim]")
        console.print()
```

**Step 3: Test CLI manually**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m cli.ivan --help`
Expected: Shows help with `comment`, `create`, and updated `done` commands

**Step 4: Commit**

```bash
git add cli/ivan/__init__.py
git commit -m "feat(cli): add comment and create commands, update done to write back"
```

---

## Task 8: Update /done Endpoint

**Files:**
- Modify: `backend/app/main.py`

The existing `/done` endpoint only updates local state. Update it to also write to the source system.

**Step 1: Update /done endpoint**

Replace the existing `mark_done` function:

```python
@app.post("/done", response_model=ActionResponse)
async def mark_done(db: Session = Depends(get_db)):
    """Mark current task as done and get next task."""
    current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

    if not current or not current.task_id:
        raise HTTPException(status_code=400, detail="No current task to complete")

    task = db.query(Task).filter(Task.id == current.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Current task not found")

    # Write to source system
    if ":" in task.id:
        source_id = task.id.split(":", 1)[1]
        writer = get_writer(task.source)
        result = await writer.complete(source_id)

        if not result.success:
            raise HTTPException(status_code=502, detail=result.message)

    # Mark as done locally
    task.status = "done"
    task.updated_at = datetime.utcnow()

    # Get next task
    remaining = (
        db.query(Task)
        .filter(
            Task.status != "done",
            Task.assignee == "ivan",
            Task.id != task.id,
        )
        .all()
    )

    db.commit()

    next_task_response = None
    if remaining:
        # Enrich with entity context and sort
        enriched = []
        for t in remaining:
            t, breakdown = enrich_task_with_entity(t)
            enriched.append((t, breakdown))
        enriched.sort(key=lambda x: x[0].score, reverse=True)

        next_task, breakdown = enriched[0]
        current.task_id = next_task.id
        current.started_at = datetime.utcnow()
        db.commit()

        next_task_response = TaskResponse(
            id=next_task.id,
            source=next_task.source,
            title=next_task.title,
            description=next_task.description,
            status=next_task.status,
            assignee=next_task.assignee,
            due_date=next_task.due_date.isoformat() if next_task.due_date else None,
            url=next_task.url,
            score=next_task.score,
            is_revenue=next_task.is_revenue,
            is_blocking=next_task.is_blocking,
            score_breakdown=breakdown,
        )

    return ActionResponse(
        success=True,
        message=f"Completed: {task.title}",
        completed_task_id=task.id,
        next_task=next_task_response,
    )
```

**Step 2: Run API tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/test_api.py -v`
Expected: PASS (all tests)

**Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(api): update /done endpoint to write back to source"
```

---

## Task 9: Documentation

**Files:**
- Create: `docs/webhook-setup.md`

**Step 1: Create webhook setup documentation**

```markdown
# Webhook Setup Guide

This guide explains how to configure webhooks for real-time task updates from ClickUp and GitHub.

## Overview

Webhooks provide instant updates when:
- Task status changes in ClickUp
- Issues are closed/reopened in GitHub
- Comments are added

Without webhooks, updates sync during the hourly sync cycle.

## ClickUp Webhook Setup

1. **Get your webhook URL:**
   ```
   https://your-app.up.railway.app/webhooks/clickup
   ```

2. **Create webhook in ClickUp:**
   - Go to ClickUp Settings → Integrations → Webhooks
   - Click "Create Webhook"
   - Endpoint URL: Your webhook URL
   - Events: Select `taskStatusUpdated`, `taskCommentPosted`
   - Space: Select your workspace

3. **Configure signature verification (recommended):**
   - Copy the webhook secret from ClickUp
   - Set `CLICKUP_WEBHOOK_SECRET` in Railway environment

## GitHub Webhook Setup

1. **Get your webhook URL:**
   ```
   https://your-app.up.railway.app/webhooks/github
   ```

2. **Create webhook in GitHub:**
   - Go to repo Settings → Webhooks → Add webhook
   - Payload URL: Your webhook URL
   - Content type: `application/json`
   - Secret: Generate a random string
   - Events: Select `Issues` and `Issue comments`

3. **Configure signature verification:**
   - Set `GITHUB_WEBHOOK_SECRET` in Railway to match the secret you entered

## Environment Variables

Add to Railway:

```
CLICKUP_WEBHOOK_SECRET=your-clickup-secret
GITHUB_WEBHOOK_SECRET=your-github-secret
```

## Testing Webhooks

1. **ClickUp:** Change a task status and check logs
2. **GitHub:** Close an issue and check logs

Logs show:
```
INFO - Task clickup:abc123 status updated to done
INFO - Issue github:42 closed externally
```

## Troubleshooting

**Webhook not triggering:**
- Check URL is publicly accessible
- Verify correct events are selected

**401 Unauthorized:**
- Signature verification failed
- Check secret matches exactly

**Task not updating:**
- Task may not be tracked (only Ivan's tasks are synced)
- Check `status: ignored` in response
```

**Step 2: Commit**

```bash
git add docs/webhook-setup.md
git commit -m "docs: add webhook setup guide"
```

---

## Task 10: Final Integration Test

**Step 1: Run all tests**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && python -m pytest backend/tests/ -v`
Expected: All tests PASS

**Step 2: Run linting**

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && ruff check backend/ cli/`
Expected: No errors

Run: `cd /Users/ivanivanka/Developer/Work/ivan-task-manager && black --check backend/ cli/`
Expected: No changes needed (or apply formatting)

**Step 3: Update STATE.md**

Update `STATE.md` with Phase 4C complete status.

**Step 4: Final commit**

```bash
git add STATE.md
git commit -m "docs(state): update for Phase 4C completion"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Writer base classes | `writers/__init__.py`, `writers/base.py`, `test_writers.py` |
| 2 | Config settings | `config.py` |
| 3 | ClickUp writer | `writers/clickup.py`, `test_writers.py` |
| 4 | GitHub writer | `writers/github.py`, `test_writers.py` |
| 5 | Write API endpoints | `main.py`, `test_api.py` |
| 6 | Webhook receivers | `webhooks.py`, `main.py`, `test_webhooks.py` |
| 7 | CLI commands | `cli/ivan/__init__.py` |
| 8 | Update /done endpoint | `main.py` |
| 9 | Documentation | `docs/webhook-setup.md` |
| 10 | Final integration | All tests, linting, STATE.md |

**Total commits:** 10
**Estimated tasks:** ~50 individual steps

---

*Plan created: 2026-01-28*
