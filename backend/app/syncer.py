"""Task synchronization from ClickUp and GitHub.

Syncs tasks hourly and caches in local database for token efficiency.
Includes retry logic with exponential backoff for resilience.
"""

import asyncio
import re
import logging
from datetime import datetime
from typing import Optional

import httpx

from .config import get_settings
from .models import Task, SyncState, SessionLocal

settings = get_settings()
logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 30.0
RETRYABLE_ERRORS = {"timeout", "connection_error", "server_error", "rate_limit"}

# User mappings
CLICKUP_USERS = {
    54476784: "ivan",
    2695145: "tamas",
    81842673: "attila",
}

GITHUB_USERS = {
    "ivanivanka": "ivan",
    "atiti": "attila",
}


class ClickUpSyncer:
    """Sync tasks from ClickUp."""

    API_BASE = "https://api.clickup.com/api/v2"

    def __init__(self):
        self.token = settings.clickup_api_token
        self.list_id = settings.clickup_list_id

    async def sync(self) -> list[Task]:
        """Fetch all tasks from ClickUp and convert to unified Task model."""
        tasks = []

        async with httpx.AsyncClient() as client:
            # Fetch open tasks
            response = await client.get(
                f"{self.API_BASE}/list/{self.list_id}/task",
                headers={"Authorization": self.token},
                params={"include_closed": "false"},
            )
            response.raise_for_status()
            data = response.json()

            for item in data.get("tasks", []):
                task = self._convert_task(item)
                if task:
                    tasks.append(task)

                    # Fetch dependencies for blocking detection
                    deps = await self._fetch_dependencies(client, item["id"])
                    task.is_blocking = deps.get("blocking", [])
                    task.blocked_by = deps.get("blocked_by", [])

        logger.info(f"Synced {len(tasks)} tasks from ClickUp")
        return tasks

    def _convert_task(self, item: dict) -> Optional[Task]:
        """Convert ClickUp task to unified Task model."""
        # Get assignee
        assignee = None
        assignees = item.get("assignees", [])
        if assignees:
            user_id = assignees[0].get("id")
            assignee = CLICKUP_USERS.get(user_id)

        # Only sync tasks assigned to Ivan
        if assignee != "ivan":
            return None

        # Normalize status
        status_name = item.get("status", {}).get("status", "").lower()
        if status_name in ["complete", "closed", "done"]:
            status = "done"
        elif status_name in ["in progress", "in_progress", "work in progress"]:
            status = "in_progress"
        else:
            status = "todo"

        # Parse due date
        due_date = None
        if item.get("due_date"):
            due_date = datetime.fromtimestamp(int(item["due_date"]) / 1000).date()

        # Check for revenue tag
        tags = [t.get("name", "").lower() for t in item.get("tags", [])]
        is_revenue = any(t in tags for t in ["revenue", "deal", "client"])

        # Parse last activity
        last_activity = None
        if item.get("date_updated"):
            last_activity = datetime.fromtimestamp(int(item["date_updated"]) / 1000)

        return Task(
            id=f"clickup:{item['id']}",
            source="clickup",
            title=item.get("name", "Untitled"),
            description=item.get("description"),
            status=status,
            assignee=assignee,
            due_date=due_date,
            url=item.get("url", ""),
            is_revenue=is_revenue,
            last_activity=last_activity,
            source_data=item,
            synced_at=datetime.utcnow(),
        )

    async def _fetch_dependencies(
        self, client: httpx.AsyncClient, task_id: str
    ) -> dict:
        """Fetch task dependencies to determine blocking relationships."""
        blocking = []
        blocked_by = []

        try:
            response = await client.get(
                f"{self.API_BASE}/task/{task_id}",
                headers={"Authorization": self.token},
            )
            response.raise_for_status()
            data = response.json()

            # Check dependencies
            for dep in data.get("dependencies", []):
                if dep.get("depends_on"):
                    blocked_by.append(f"clickup:{dep['depends_on']}")

            # Check dependents (tasks waiting on this one)
            for dep in data.get("dependents", []):
                # Get assignee of dependent task
                dep_assignees = dep.get("assignees", [])
                for a in dep_assignees:
                    user = CLICKUP_USERS.get(a.get("id"))
                    if user and user != "ivan":
                        blocking.append(user)

        except Exception as e:
            logger.warning(f"Failed to fetch dependencies for {task_id}: {e}")

        return {"blocking": blocking, "blocked_by": blocked_by}


class GitHubSyncer:
    """Sync issues from GitHub."""

    API_BASE = "https://api.github.com"

    def __init__(self):
        self.token = settings.github_token
        self.repo = settings.github_repo

    async def sync(self) -> list[Task]:
        """Fetch all issues assigned to Ivan and convert to unified Task model."""
        tasks = []

        async with httpx.AsyncClient() as client:
            # Fetch issues assigned to ivanivanka
            response = await client.get(
                f"{self.API_BASE}/repos/{self.repo}/issues",
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={
                    "assignee": "ivanivanka",
                    "state": "open",
                },
            )
            response.raise_for_status()
            data = response.json()

            for item in data:
                # Skip pull requests
                if "pull_request" in item:
                    continue

                task = self._convert_issue(item)
                if task:
                    tasks.append(task)

        logger.info(f"Synced {len(tasks)} issues from GitHub")
        return tasks

    def _convert_issue(self, item: dict) -> Optional[Task]:
        """Convert GitHub issue to unified Task model."""
        # Normalize status
        state = item.get("state", "open")
        status = "done" if state == "closed" else "todo"

        # Check labels for revenue/client
        labels = [lbl.get("name", "").lower() for lbl in item.get("labels", [])]
        is_revenue = any(
            "client" in lbl or "revenue" in lbl or "deal" in lbl for lbl in labels
        )

        # Parse blocking from body
        blocking, blocked_by = self._parse_blocking(item.get("body", ""))

        # Parse last activity
        last_activity = None
        if item.get("updated_at"):
            last_activity = datetime.fromisoformat(
                item["updated_at"].replace("Z", "+00:00")
            )

        return Task(
            id=f"github:{item['number']}",
            source="github",
            title=item.get("title", "Untitled"),
            description=item.get("body"),
            status=status,
            assignee="ivan",
            due_date=None,  # GitHub issues don't have native due dates
            url=item.get("html_url", ""),
            is_revenue=is_revenue,
            is_blocking_json=blocking,
            blocked_by_json=blocked_by,
            last_activity=last_activity,
            source_data=item,
            synced_at=datetime.utcnow(),
        )

    def _parse_blocking(self, body: str) -> tuple[list[str], list[str]]:
        """Parse 'Blocked by #X' and 'Blocks #Y' from issue body."""
        blocking = []
        blocked_by = []

        if not body:
            return blocking, blocked_by

        # Find "Blocked by #X" patterns
        blocked_pattern = re.findall(r"[Bb]locked\s+by\s+#(\d+)", body)
        for issue_num in blocked_pattern:
            blocked_by.append(f"github:{issue_num}")

        # Find "Blocks #X" patterns - these mean someone is waiting
        blocks_pattern = re.findall(r"[Bb]locks\s+#(\d+)", body)
        if blocks_pattern:
            # Simplified: assume blocking someone (would need to fetch assignee for accuracy)
            blocking.append("unknown")

        return blocking, blocked_by


def _categorize_error(e: Exception) -> tuple[str, str]:
    """Categorize an exception into error type and message.

    Returns (error_type, error_message) tuple.
    """
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return "auth_error", "Authentication failed - check API token"
        elif status == 403:
            return "permission_error", "Permission denied - check API permissions"
        elif status == 404:
            return "not_found", "Resource not found - check list/repo ID"
        elif status == 429:
            return "rate_limit", "Rate limit exceeded - will retry later"
        elif status >= 500:
            return "server_error", f"Server error ({status}) - source may be down"
        else:
            return "http_error", f"HTTP error {status}: {e.response.text[:100]}"
    elif isinstance(e, httpx.TimeoutException):
        return "timeout", "Request timed out - network may be slow"
    elif isinstance(e, httpx.ConnectError):
        return "connection_error", "Could not connect - check network"
    elif isinstance(e, httpx.RequestError):
        return "request_error", f"Request failed: {str(e)}"
    else:
        return "unknown_error", str(e)


def _update_sync_state(
    db, source: str, status: str, error_message: Optional[str] = None
):
    """Update sync state for a source."""
    sync_state = db.query(SyncState).filter(SyncState.source == source).first()
    if not sync_state:
        sync_state = SyncState(source=source)
        db.add(sync_state)
    sync_state.last_sync = datetime.utcnow()
    sync_state.status = status
    sync_state.error_message = error_message


async def _sync_with_retry(syncer) -> list[Task]:
    """Sync with exponential backoff retry for transient errors.

    Retries on: timeout, connection_error, server_error, rate_limit.
    Fails immediately on: auth_error, permission_error, not_found.
    """
    last_exception = None
    last_error_type = None

    for attempt in range(MAX_RETRIES):
        try:
            return await syncer.sync()
        except Exception as e:
            error_type, error_message = _categorize_error(e)
            last_exception = e
            last_error_type = error_type

            # Don't retry non-transient errors
            if error_type not in RETRYABLE_ERRORS:
                logger.warning(f"Non-retryable error ({error_type}): {error_message}")
                raise

            # Calculate delay with exponential backoff
            delay = min(
                BASE_DELAY_SECONDS * (2**attempt),
                MAX_DELAY_SECONDS,
            )

            logger.warning(
                f"Attempt {attempt + 1}/{MAX_RETRIES} failed ({error_type}): "
                f"{error_message}. Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error(f"All {MAX_RETRIES} retry attempts failed ({last_error_type})")
    raise last_exception


async def _sync_source(syncer, source_name: str, db) -> tuple[int, Optional[str]]:
    """Sync a single source with error handling and retry logic.

    Returns (task_count, error_message or None).
    """
    try:
        # Use retry wrapper for transient errors
        tasks = await _sync_with_retry(syncer)

        for task in tasks:
            existing = db.query(Task).filter(Task.id == task.id).first()
            if existing:
                for key, value in task.__dict__.items():
                    if not key.startswith("_"):
                        setattr(existing, key, value)
            else:
                db.add(task)

        _update_sync_state(db, source_name, "success")
        return len(tasks), None

    except Exception as e:
        error_type, error_message = _categorize_error(e)
        logger.error(f"{source_name} sync failed ({error_type}): {error_message}")
        _update_sync_state(db, source_name, "error", error_message)
        return 0, f"{source_name}: {error_message}"


async def sync_all_sources() -> dict:
    """Sync tasks from all sources and update database.

    Each source syncs independently - failures in one don't affect others.
    Returns dict with task counts per source and any errors.
    """
    db = SessionLocal()

    try:
        results = {"clickup": 0, "github": 0, "errors": []}

        # Sync ClickUp
        if settings.clickup_api_token:
            count, error = await _sync_source(ClickUpSyncer(), "clickup", db)
            results["clickup"] = count
            if error:
                results["errors"].append(error)
        else:
            logger.warning("Skipping ClickUp sync - no API token configured")
            results["errors"].append("ClickUp: No API token configured")

        # Sync GitHub
        if settings.github_token:
            count, error = await _sync_source(GitHubSyncer(), "github", db)
            results["github"] = count
            if error:
                results["errors"].append(error)
        else:
            logger.warning("Skipping GitHub sync - no token configured")
            results["errors"].append("GitHub: No token configured")

        db.commit()

        # Log summary
        total = results["clickup"] + results["github"]
        if results["errors"]:
            logger.warning(
                f"Sync completed with errors: {total} tasks synced, "
                f"{len(results['errors'])} sources failed"
            )
        else:
            logger.info(f"Sync completed successfully: {total} tasks synced")

        return results

    finally:
        db.close()
