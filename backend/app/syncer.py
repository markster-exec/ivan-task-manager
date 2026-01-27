"""Task synchronization from ClickUp and GitHub.

Syncs tasks hourly and caches in local database for token efficiency.
"""

import re
import logging
from datetime import datetime
from typing import Optional

import httpx

from .config import get_settings
from .models import Task, SyncState, SessionLocal

settings = get_settings()
logger = logging.getLogger(__name__)

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


async def sync_all_sources() -> dict:
    """Sync tasks from all sources and update database."""
    db = SessionLocal()

    try:
        results = {"clickup": 0, "github": 0, "errors": []}

        # Sync ClickUp
        try:
            clickup_syncer = ClickUpSyncer()
            clickup_tasks = await clickup_syncer.sync()
            for task in clickup_tasks:
                existing = db.query(Task).filter(Task.id == task.id).first()
                if existing:
                    # Update existing
                    for key, value in task.__dict__.items():
                        if not key.startswith("_"):
                            setattr(existing, key, value)
                else:
                    db.add(task)
            results["clickup"] = len(clickup_tasks)

            # Update sync state
            sync_state = (
                db.query(SyncState).filter(SyncState.source == "clickup").first()
            )
            if not sync_state:
                sync_state = SyncState(source="clickup")
                db.add(sync_state)
            sync_state.last_sync = datetime.utcnow()
            sync_state.status = "success"

        except Exception as e:
            logger.error(f"ClickUp sync failed: {e}")
            results["errors"].append(f"ClickUp: {str(e)}")

        # Sync GitHub
        try:
            github_syncer = GitHubSyncer()
            github_tasks = await github_syncer.sync()
            for task in github_tasks:
                existing = db.query(Task).filter(Task.id == task.id).first()
                if existing:
                    for key, value in task.__dict__.items():
                        if not key.startswith("_"):
                            setattr(existing, key, value)
                else:
                    db.add(task)
            results["github"] = len(github_tasks)

            # Update sync state
            sync_state = (
                db.query(SyncState).filter(SyncState.source == "github").first()
            )
            if not sync_state:
                sync_state = SyncState(source="github")
                db.add(sync_state)
            sync_state.last_sync = datetime.utcnow()
            sync_state.status = "success"

        except Exception as e:
            logger.error(f"GitHub sync failed: {e}")
            results["errors"].append(f"GitHub: {str(e)}")

        db.commit()
        return results

    finally:
        db.close()
