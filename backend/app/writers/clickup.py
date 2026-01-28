"""ClickUp writer implementation.

TODO: Implement in Task 3.
"""

from typing import Optional

from .base import SourceWriter, WriteResult


class ClickUpWriter(SourceWriter):
    """Writer for ClickUp tasks.

    Stub implementation - will be completed in Task 3.
    """

    async def complete(self, source_id: str) -> WriteResult:
        """Mark task complete in ClickUp."""
        raise NotImplementedError("ClickUpWriter.complete not yet implemented")

    async def comment(self, source_id: str, text: str) -> WriteResult:
        """Add comment to ClickUp task."""
        raise NotImplementedError("ClickUpWriter.comment not yet implemented")

    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
        **kwargs,
    ) -> WriteResult:
        """Create new task in ClickUp."""
        raise NotImplementedError("ClickUpWriter.create not yet implemented")
