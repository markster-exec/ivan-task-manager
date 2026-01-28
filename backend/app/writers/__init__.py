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
