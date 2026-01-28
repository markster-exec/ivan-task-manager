"""GitHub writer for updating issues."""

from typing import Optional

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
        self._client: Optional[httpx.AsyncClient] = None

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
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
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
