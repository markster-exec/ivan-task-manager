---
id: phase-4b-entity-awareness-design
title: Phase 4B Entity Awareness Design
type: plan
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [phase-4, entity-awareness, design]
---

# Phase 4B: Entity Awareness Design

## Overview

Tasks know their context (who, what project, why it matters). Enables queries like "What's happening with Mark?" and gives AI the context to prioritize intelligently.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | YAML files only (DB on roadmap) | Simple, version-controlled, ~20 entities max for now |
| Task-entity mapping | Explicit tags + manual overrides | Others create tasks too; overrides handle exceptions |
| Schema | Full schema (all fields) | Task manager = central hub with everything to act |
| Workstream linking | Tag-based + default to first active | Simple tags, precision when needed |
| Override format | Single `mappings.yaml` file | One place to check for exceptions |
| Scoring | Add project urgency + entity priority | Relationship type default + manual override |
| Display | Inline context + URLs always | Tell user where to go to work |
| Entity queries | `ivan entity <name>` shows everything | One command, full picture |

## Data Model

### Directory Structure

```
entities/
├── mark-smith.yaml
├── kyle-stearns.yaml
└── mappings.yaml          # Task overrides
```

### Entity Schema

```yaml
# Required fields
id: mark-smith                          # Unique slug
type: person                            # person | company
name: Mark Smith                        # Display name
created: 2026-01-28                     # ISO date
updated: 2026-01-28                     # ISO date
tags: [client, priority]                # For filtering

# Optional identity
company: AI Branding Academy
email: mark@example.com
linkedin: https://linkedin.com/in/...
phone: "+1-555-..."

# Relationship
relationship_type: client               # client|prospect|partner|investor|team|vendor|network
priority: 5                             # Override (1-5, default from relationship_type)
intention: "Showcase client → channel partner"

# Workstreams (projects/initiatives)
workstreams:
  - id: workshop
    name: Workshop Success
    status: active                      # planned|active|blocked|complete
    deadline: 2026-02-15
    milestone: "Live workshop"
    revenue_potential: "$10,000+"

  - id: system-setup
    name: System Setup
    status: complete
    deadline: 2026-01-25

# Cross-references (where to work)
channels:
  github: "markster-exec/project-tracker#16"
  clickup: "869bxxuwr"
  gdoc: "1byTVcZUJ7RXSOWTlYhJ7pQiARarBNNUB"
  slack: "#mark-smith"

# Context for AI
context_summary: |
  Building AI Branding Academy. Setting up on Markster as showcase.
  Success = case study + partnership. Workshop in mid-Feb is key milestone.
```

### Mappings File (Overrides)

```yaml
# entities/mappings.yaml
task_overrides:
  "clickup:869bxxud4":
    entity: mark-smith
    workstream: workshop

  "github:42":
    entity: kyle-stearns
    # no workstream = use default (first active)
```

## Task-Entity Mapping

### Mapping Priority

1. **Manual overrides** — Check `mappings.yaml` first
2. **Explicit tags** — Parse from title/tags
3. **Default workstream** — First `active` workstream if only entity specified

### Tag Formats

| Source | Format | Example |
|--------|--------|---------|
| GitHub title | `[CLIENT:entity]` or `[CLIENT:entity:workstream]` | `[CLIENT:mark-smith] Write blog post` |
| ClickUp tag | `client:entity` or `client:entity:workstream` | `client:mark-smith:workshop` |

### Mapping Logic

```python
def map_task_to_entity(task: Task) -> tuple[str, str] | None:
    """Returns (entity_id, workstream_id) or None."""

    # 1. Check manual overrides first
    if override := get_override(task.id):
        return override

    # 2. Parse from title: [CLIENT:entity:workstream]
    if match := parse_client_tag(task.title):
        return match

    # 3. Parse from ClickUp tags: client:entity:workstream
    if task.source == "clickup":
        if match := parse_clickup_tags(task.source_data):
            return match

    return None

def get_default_workstream(entity: Entity) -> str | None:
    """Return first active workstream ID."""
    for ws in entity.workstreams:
        if ws.status == "active":
            return ws.id
    return None
```

## Enhanced Scoring

### Formula

```
Score = (Revenue × 1000)
      + (Blocking × 500 × count)
      + (Task Urgency × 100)
      + (Project Urgency × 50)      # NEW
      + (Entity Priority × 25)      # NEW
      + Recency
```

### Project Urgency

Inherited from workstream deadline when task has no deadline:

| Workstream Deadline | Urgency | Points |
|---------------------|---------|--------|
| Overdue | 5 | +250 |
| Due today | 4 | +200 |
| Due this week | 3 | +150 |
| Future / none | 1 | +50 |

### Entity Priority

Default from relationship type, override with `priority:` field:

```python
RELATIONSHIP_DEFAULTS = {
    "team": 5,
    "client": 4,
    "investor": 4,
    "prospect": 3,
    "partner": 3,
    "vendor": 1,
    "network": 1,
}
```

Score contribution: `priority × 25` (max +125 points)

### Example

```
Task: [WRITE] Blog post for Mark
- No deadline on task
- Workstream "Workshop" due in 3 days → Project Urgency = 3 → +150
- Mark is client (4) with override priority 5 → +125
- Total boost: +275 points
```

## Display Formats

### `ivan next` (enhanced)

```
#1: [WRITE] Blog post about X
    Score: 1375 | Due: Jan 30 | Revenue
    → Mark Smith (AI Branding Academy) — Workshop by Feb 15
    Task: https://app.clickup.com/t/869bxxud4
    Brief: https://docs.google.com/document/d/1byTVc...
```

### `ivan context [task_number]`

```
Mark Smith — AI Branding Academy
Intention: Showcase client → channel partner
Priority: 5 (client)

Workstream: Workshop Success
  Status: active | Deadline: Feb 15
  Milestone: Live workshop
  Revenue: $10,000+

Where to work:
  Task:   https://app.clickup.com/t/869bxxud4
  Brief:  https://docs.google.com/document/d/1byTVc...
  GitHub: https://github.com/markster-exec/project-tracker/issues/16
  Slack:  #mark-smith

Context:
  Building AI Branding Academy. Setting up on Markster as showcase.
  Success = case study + partnership.
```

### `ivan entity <name>`

```
Mark Smith — AI Branding Academy
  Email: mark@example.com
  Phone: +1-555-...
  Type: client | Priority: 5

Intention: Showcase client → channel partner

Workstreams:
  [active]   Workshop Success — due Feb 15 ($10,000+)
  [complete] System Setup — done Jan 25

Tasks (3):
  #1: [WRITE] Blog post (Score: 1375)
  #4: [REVIEW] System docs (Score: 850)
  #7: [CALL] Follow-up (Score: 600)

Channels:
  Brief:  https://docs.google.com/document/d/1byTVc...
  GitHub: https://github.com/markster-exec/project-tracker/issues/16
```

### `ivan projects`

```
ACTIVE WORKSTREAMS

Mark Smith (AI Branding Academy)
  → Workshop Success — due Feb 15 (3 tasks)

Kyle Stearns (Ace Industrial)
  → Voice AI Setup — due Feb 1 (2 tasks)

---
BLOCKED

(none)
```

## Module Structure

### New Files

```
entities/                           # NEW directory
├── mark-smith.yaml                 # Example entity
├── kyle-stearns.yaml               # Example entity
└── mappings.yaml                   # Task overrides

backend/app/
├── entity_loader.py                # NEW: Load entities from YAML
├── entity_mapper.py                # NEW: Map tasks to entities
├── entity_models.py                # NEW: Pydantic models for entities
├── scorer.py                       # UPDATE: Add project/entity scoring
└── main.py                         # UPDATE: Add entity endpoints

cli/ivan/
└── __init__.py                     # UPDATE: Add entity, context, projects commands
```

### Pydantic Models

```python
# entity_models.py

class Workstream(BaseModel):
    id: str
    name: str
    status: Literal["planned", "active", "blocked", "complete"]
    deadline: date | None = None
    milestone: str | None = None
    revenue_potential: str | None = None

class Entity(BaseModel):
    id: str
    type: Literal["person", "company"]
    name: str
    created: date
    updated: date
    tags: list[str] = []

    # Optional identity
    company: str | None = None
    email: str | None = None
    linkedin: str | None = None
    phone: str | None = None

    # Relationship
    relationship_type: str | None = None
    priority: int | None = None
    intention: str | None = None

    # Workstreams & channels
    workstreams: list[Workstream] = []
    channels: dict[str, str] = {}
    context_summary: str | None = None

    def get_priority(self) -> int:
        """Return priority, defaulting from relationship_type."""
        if self.priority:
            return self.priority
        defaults = {
            "team": 5, "client": 4, "investor": 4,
            "prospect": 3, "partner": 3,
            "vendor": 1, "network": 1,
        }
        return defaults.get(self.relationship_type, 2)

    def get_active_workstream(self) -> Workstream | None:
        """Return first active workstream."""
        for ws in self.workstreams:
            if ws.status == "active":
                return ws
        return None
```

### Entity Loader

```python
# entity_loader.py

from pathlib import Path
import yaml
from .entity_models import Entity

_entities: dict[str, Entity] = {}
_mappings: dict[str, dict] = {}

def load_entities(entities_dir: Path) -> None:
    """Load all entity YAML files into memory."""
    global _entities, _mappings
    _entities = {}
    _mappings = {}

    for yaml_file in entities_dir.glob("*.yaml"):
        if yaml_file.name == "mappings.yaml":
            _mappings = yaml.safe_load(yaml_file.read_text()).get("task_overrides", {})
        else:
            data = yaml.safe_load(yaml_file.read_text())
            entity = Entity(**data)
            _entities[entity.id] = entity

def get_entity(entity_id: str) -> Entity | None:
    return _entities.get(entity_id)

def get_all_entities() -> list[Entity]:
    return list(_entities.values())

def get_override(task_id: str) -> tuple[str, str | None] | None:
    if task_id in _mappings:
        override = _mappings[task_id]
        return (override["entity"], override.get("workstream"))
    return None
```

## API Endpoints

```
GET /entities                    # List all entities (summary)
GET /entities/{id}               # Full entity detail
GET /entities/{id}/tasks         # Tasks for entity
GET /tasks/{id}/context          # Entity context for a task
POST /entities/reload            # Reload from YAML files
```

## Bot Integration

### "What's next?" Response

```
Your top task:

*[WRITE] Blog post about X*
Score: 1375 | Due: Jan 30 | 💰 Revenue

→ Mark Smith (AI Branding Academy) — Workshop by Feb 15
<https://app.clickup.com/t/869bxxud4|Open in ClickUp> · <https://docs.google.com/.../|Brief>
```

### Entity Query ("What's happening with Mark?")

```
*Mark Smith* — AI Branding Academy
Priority: ⭐⭐⭐⭐⭐ (client)

*Active:* Workshop Success — due Feb 15
3 tasks, top one: [WRITE] Blog post (Score: 1375)

<https://docs.google.com/.../|Brief> · <https://github.com/.../|GitHub>
```

### Bot Commands

| Command | Action |
|---------|--------|
| `entity mark` | Entity lookup by name |
| `what's happening with mark` | Entity lookup (natural language) |
| `context` | Context for current task |
| `projects` | List all active workstreams |

## Future Considerations (Roadmap)

- **Database caching** — When entities grow beyond ~50, add SQLAlchemy models and sync from YAML
- **Entity relationships** — Link entities to each other (Mark works at Company X)
- **Auto-discovery** — Suggest entity creation from task patterns

## Acceptance Criteria

- [ ] Can create entity YAML file and system loads it
- [ ] Tasks with `[CLIENT:Mark]` in title are linked to Mark entity
- [ ] Tasks with `client:mark` ClickUp tag are linked to Mark entity
- [ ] Manual override in `mappings.yaml` works
- [ ] Task without deadline but in workstream with deadline shows workstream deadline
- [ ] `ivan next` shows: entity name, workstream, why urgent, URLs
- [ ] `ivan context` shows full entity detail with all channels
- [ ] `ivan entity mark` shows all tasks/workstreams for Mark
- [ ] `ivan projects` shows all entities grouped by workstream status
- [ ] Scoring reflects project urgency and entity priority
- [ ] Bot responds to "what's happening with mark"

---

*Brainstormed: 2026-01-28*
