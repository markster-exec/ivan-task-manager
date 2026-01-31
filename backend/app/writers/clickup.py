"""ClickUp writer for updating tasks."""

from datetime import date
from typing import Optional

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
        self._client: Optional[httpx.AsyncClient] = None

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
            current_status = get_resp.json().get("status", {}).get("status", "").lower()

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
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
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

    async def update_due_date(self, source_id: str, new_date: date) -> WriteResult:
        """Update task due date in ClickUp."""
        try:
            client = await self._get_client()

            # ClickUp expects due_date as Unix timestamp in milliseconds
            from datetime import datetime, timezone

            due_timestamp = int(
                datetime.combine(new_date, datetime.min.time())
                .replace(tzinfo=timezone.utc)
                .timestamp()
                * 1000
            )

            response = await client.put(
                f"{self.API_BASE}/task/{source_id}",
                json={"due_date": due_timestamp},
            )
            response.raise_for_status()
            return WriteResult(
                success=True, message=f"Due date updated to {new_date} in ClickUp"
            )

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"ClickUp error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")

    async def reassign(self, source_id: str, assignee_id: str) -> WriteResult:
        """Reassign task to another user in ClickUp."""
        try:
            client = await self._get_client()

            # First get current assignees to replace them
            get_resp = await client.get(f"{self.API_BASE}/task/{source_id}")
            get_resp.raise_for_status()
            current_assignees = [
                str(a["id"]) for a in get_resp.json().get("assignees", [])
            ]

            # Update assignees: remove current, add new
            response = await client.put(
                f"{self.API_BASE}/task/{source_id}",
                json={
                    "assignees": {
                        "rem": current_assignees,
                        "add": [assignee_id],
                    }
                },
            )
            response.raise_for_status()
            return WriteResult(success=True, message="Task reassigned in ClickUp")

        except httpx.HTTPStatusError as e:
            return WriteResult(
                success=False, message=f"ClickUp error: {e.response.status_code}"
            )
        except httpx.RequestError as e:
            return WriteResult(success=False, message=f"Connection error: {e}")
