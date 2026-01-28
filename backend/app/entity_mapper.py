"""Map tasks to entities based on tags, titles, and overrides."""

import re
import logging
from typing import Optional

from .models import Task
from .entity_loader import get_entity, get_override

logger = logging.getLogger(__name__)

# Pattern for [CLIENT:entity] or [CLIENT:entity:workstream] in titles
CLIENT_TAG_PATTERN = re.compile(
    r"\[CLIENT:([a-z0-9-]+)(?::([a-z0-9-]+))?\]", re.IGNORECASE
)


def parse_client_tag(title: str) -> Optional[tuple[str, Optional[str]]]:
    """Parse [CLIENT:entity:workstream] from task title.

    Args:
        title: Task title

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id may be None.
    """
    match = CLIENT_TAG_PATTERN.search(title)
    if match:
        entity_id = match.group(1).lower()
        workstream_id = match.group(2).lower() if match.group(2) else None
        return (entity_id, workstream_id)
    return None


def parse_clickup_tags(
    source_data: Optional[dict],
) -> Optional[tuple[str, Optional[str]]]:
    """Parse client:entity:workstream from ClickUp tags.

    Args:
        source_data: Raw ClickUp API response

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id may be None.
    """
    if not source_data:
        return None

    tags = source_data.get("tags", [])
    for tag in tags:
        tag_name = tag.get("name", "").lower()
        if tag_name.startswith("client:"):
            parts = tag_name.split(":")
            if len(parts) >= 2:
                entity_id = parts[1].lower()
                workstream_id = parts[2].lower() if len(parts) >= 3 else None
                return (entity_id, workstream_id)

    return None


def resolve_workstream(entity_id: str, workstream_id: Optional[str]) -> Optional[str]:
    """Resolve workstream ID, defaulting to first active if not specified.

    Args:
        entity_id: The entity ID
        workstream_id: The workstream ID (may be None)

    Returns:
        Resolved workstream ID or None
    """
    entity = get_entity(entity_id)
    if not entity:
        return None

    if workstream_id:
        # Verify workstream exists
        if entity.get_workstream(workstream_id):
            return workstream_id
        logger.warning(
            f"Workstream '{workstream_id}' not found for entity '{entity_id}'"
        )
        # Fall through to default

    # Default to first active workstream
    active = entity.get_active_workstream()
    return active.id if active else None


def map_task_to_entity(task: Task) -> Optional[tuple[str, Optional[str]]]:
    """Map a task to an entity and workstream.

    Priority:
    1. Manual overrides (mappings.yaml)
    2. [CLIENT:entity:workstream] in title
    3. client:entity:workstream ClickUp tag

    Args:
        task: The task to map

    Returns:
        Tuple of (entity_id, workstream_id) or None.
        workstream_id resolved to first active if not specified.
    """
    # 1. Check manual overrides first
    override = get_override(task.id)
    if override:
        entity_id, workstream_id = override
        if get_entity(entity_id):
            resolved_ws = resolve_workstream(entity_id, workstream_id)
            return (entity_id, resolved_ws)
        logger.warning(f"Override entity '{entity_id}' not found for task '{task.id}'")

    # 2. Parse from title
    title_match = parse_client_tag(task.title)
    if title_match:
        entity_id, workstream_id = title_match
        if get_entity(entity_id):
            resolved_ws = resolve_workstream(entity_id, workstream_id)
            return (entity_id, resolved_ws)
        logger.warning(f"Title entity '{entity_id}' not found for task '{task.id}'")

    # 3. Parse from ClickUp tags
    if task.source == "clickup":
        tag_match = parse_clickup_tags(task.source_data)
        if tag_match:
            entity_id, workstream_id = tag_match
            if get_entity(entity_id):
                resolved_ws = resolve_workstream(entity_id, workstream_id)
                return (entity_id, resolved_ws)
            logger.warning(f"Tag entity '{entity_id}' not found for task '{task.id}'")

    return None
