"""GitHub writer implementation.

TODO: Implement in Task 4.
"""

from typing import Optional

from .base import SourceWriter, WriteResult


class GitHubWriter(SourceWriter):
    """Writer for GitHub issues.

    Stub implementation - will be completed in Task 4.
    """

    async def complete(self, source_id: str) -> WriteResult:
        """Close GitHub issue."""
        raise NotImplementedError("GitHubWriter.complete not yet implemented")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to GitHub issue."""
        raise NotImplementedError("GitHubWriter.comment not yet implemented")

    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
        **kwargs,
    ) -> WriteResult:
        """Create new GitHub issue."""
        raise NotImplementedError("GitHubWriter.create not yet implemented")
