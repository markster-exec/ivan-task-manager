"""Base classes for source writers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


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
    source_id: Optional[str] = None
    conflict: bool = False
    current_state: Optional[str] = None


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
        description: Optional[str] = None,
        entity_id: Optional[str] = None,
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
