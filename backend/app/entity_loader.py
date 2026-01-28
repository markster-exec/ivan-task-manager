"""Load entities from YAML files."""

import logging
from pathlib import Path
from typing import Optional, Union

import yaml
from yaml import YAMLError
from pydantic import ValidationError

from .entity_models import Entity

logger = logging.getLogger(__name__)

# In-memory cache
_entities: dict[str, Entity] = {}
_mappings: dict[str, dict[str, Optional[str]]] = {}


def load_entities(entities_dir: Path) -> None:
    """Load all entity YAML files into memory.

    Args:
        entities_dir: Path to the entities/ directory
    """
    global _entities, _mappings
    _entities = {}
    _mappings = {}

    if not entities_dir.exists():
        logger.warning(f"Entities directory not found: {entities_dir}")
        return

    for yaml_file in entities_dir.glob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text())

            if yaml_file.name == "mappings.yaml":
                _mappings = data.get("task_overrides", {})
                logger.info(f"Loaded {len(_mappings)} task overrides")
            else:
                entity = Entity(**data)
                _entities[entity.id] = entity
                logger.debug(f"Loaded entity: {entity.id}")

        except YAMLError as e:
            logger.error(f"Invalid YAML in {yaml_file.name}: {e}")
        except ValidationError as e:
            logger.error(f"Invalid entity data in {yaml_file.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to load {yaml_file.name}: {type(e).__name__}: {e}")

    logger.info(f"Loaded {len(_entities)} entities")


def get_entity(entity_id: str) -> Optional[Entity]:
    """Get entity by ID.

    Args:
        entity_id: The entity ID (slug)

    Returns:
        Entity or None if not found
    """
    return _entities.get(entity_id)


def get_all_entities() -> list[Entity]:
    """Get all loaded entities.

    Returns:
        List of all entities
    """
    return list(_entities.values())


def get_override(task_id: str) -> Optional[tuple[str, Optional[str]]]:
    """Get manual override mapping for a task.

    Args:
        task_id: The task ID (e.g., "clickup:869bxxud4")

    Returns:
        Tuple of (entity_id, workstream_id) or None if no override.
        workstream_id may be None if only entity is specified.
    """
    if task_id not in _mappings:
        return None

    override = _mappings[task_id]
    if "entity" not in override:
        logger.warning(f"Invalid override for {task_id}: missing 'entity' key")
        return None

    return (override["entity"], override.get("workstream"))


def find_entity_by_name(name: str) -> Optional[Entity]:
    """Find entity by name (case-insensitive partial match).

    Args:
        name: Name to search for

    Returns:
        First matching entity or None
    """
    name_lower = name.lower()
    for entity in _entities.values():
        if name_lower in entity.name.lower():
            return entity
        if name_lower in entity.id.lower():
            return entity
    return None
