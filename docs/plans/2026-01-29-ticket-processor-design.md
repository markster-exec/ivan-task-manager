# Ticket Processor Design

> Automatically process GitHub tickets: respond when possible, create tasks when human action needed.

## Overview

The Ticket Processor is a Layer 4 (Execution) capability for ivan-task-manager. It analyzes tickets, drafts responses, and either executes actions automatically (with approval) or creates tasks for manual work.

**Key principle:** The processor creates Tasks. Those tasks flow through the existing `ivan next` → `ivan done` pipeline. No parallel systems.

## Architecture

```
                    ivan process
                         ↓
              Creates Tasks (with actions)
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
           ONLINE                OFFLINE
              ↓                     ↓
         ivan next              export
              ↓                     ↓
         ivan done              ivan-os
              ↓                     ↓
         posts to GitHub        decisions
                                    ↓
                                import
                                    ↓
                               ivan next
                                    ↓
                               ivan done
                                    ↓
                               posts to GitHub
```

### System Boundaries

| System | Responsibility |
|--------|----------------|
| ivan-task-manager | Process tickets, create tasks with actions, export/import, execute actions |
| ivan-os | Offline review, decision capture, outbox for sync back |
| GitHub | Source of tickets, destination for responses |
| ClickUp (Agent Queue) | Tasks requiring manual human work |

### Task Destinations

| Processor output | Destination |
|------------------|-------------|
| Agent can respond/act | Task in ivan-task-manager (source=processor, has action) |
| Human must do manual work | Task in ClickUp Agent Queue (list 901215555715) |

## Data Model

### Task.action Field

New JSON field on Task model for processor-generated tasks:

```python
action = {
    "type": "github_comment",  # or: github_close, github_label, pr_create
    "issue": 31,
    "repo": "markster-exec/project-tracker",
    "body": "Keep it open until we increase the MailReef limit."
}
```

### Processor Task

```python
Task(
    id="proc-31-abc123",
    source="processor",
    title="Respond to #31: close or keep open?",
    description="Attila asked whether to close or keep open...",
    url="https://github.com/markster-exec/project-tracker/issues/31",
    status="pending",
    entity_id="mark-de-grasse",
    score=85,  # Scored like any task
    action={...},
    linked_task_id="github:31"  # Reference to original ticket
)
```

## Processing Logic

### Classification

The processor answers two questions:

1. **Is there something actionable for Ivan?**
   - `@ivanivanka` mention with question mark
   - Ticket assigned to Ivan, still open
   - Waiting for Ivan's input (no recent response)

2. **Can agent handle it?**
   - Response/comment → yes
   - Code in our repos → yes
   - External tool (GHL, Make, etc.) → no → ClickUp task
   - Business decision with implications → no → ClickUp task

### Execution Flow

```python
def process_ticket(ticket):
    # 1. Find what needs doing
    action_needed = find_pending_action(ticket)
    if not action_needed:
        return  # Nothing to do

    # 2. Can agent handle it?
    if requires_external_tool(action_needed):
        create_clickup_task(action_needed, list_id=AGENT_QUEUE)
        return

    if requires_business_decision(action_needed):
        create_clickup_task(action_needed, list_id=AGENT_QUEUE)
        return

    # 3. Agent can handle - draft response
    draft = generate_response(action_needed, ticket)

    # 4. Create processor task
    create_processor_task(
        ticket=ticket,
        draft=draft,
        action_type="github_comment"
    )
```

### Response Generation

Uses entity context for informed responses:

```python
def generate_response(action, ticket):
    entity = load_entity(ticket.entity_id)
    workstream = get_active_workstream(entity)

    context = f"""
    Entity: {entity.name} ({entity.relationship_type})
    Workstream: {workstream.name if workstream else 'None'}
    Intention: {entity.intention}

    Ticket: {ticket.title}
    Question: {action.question}
    History: {ticket.comments[-5:]}  # Recent context
    """

    return draft_response(context)
```

## CLI Commands

### ivan process

```bash
ivan process [--limit N] [--dry-run]
```

- Processes open tickets in priority order
- Creates processor tasks (with actions) or ClickUp tasks (manual work)
- Reports summary: "Processed 8 tickets: 3 drafts ready, 2 need manual work, 3 no action"

### ivan next (modified)

When showing a processor task:

```
┌─────────────────────────────────────────────────────────────────┐
│ Respond to #31: close or keep open?                             │
├─────────────────────────────────────────────────────────────────┤
│ Score: 85 | Revenue | Mark De Grasse                            │
│ → AI Branding Academy - Email infrastructure                    │
│                                                                 │
│ Attila asked: "Close this task for the time being?              │
│ or keep it open until we can add all mailboxes?"                │
│                                                                 │
│ Draft response:                                                 │
│ ┌─────────────────────────────────────────────────────────────┐ │
│ │ Keep it open - we'll add the remaining mailboxes once we    │ │
│ │ increase the MailReef limit or clean up unused accounts.    │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│ On done: Posts comment to GitHub #31                            │
└─────────────────────────────────────────────────────────────────┘

[done] post as-is  [done -e] edit first  [skip] next task
```

### ivan done (modified)

When completing a processor task:

```python
def handle_done(task):
    if task.action:
        # Execute the action
        if task.action["type"] == "github_comment":
            github_writer.post_comment(
                repo=task.action["repo"],
                issue=task.action["issue"],
                body=task.action["body"]
            )
        # Mark complete
        task.status = "done"
        # Update linked ticket
        update_linked_task(task.linked_task_id)
    else:
        # Normal done behavior
        mark_complete_in_source(task)
```

### ivan done -e (edit before posting)

Opens editor with draft, saves edited version, then posts.

## Export/Import (Offline Support)

### Export Bundle Structure

```
ivan-os/data/sync/
├── tasks.db              # All tasks including processor tasks
├── entities/             # Entity YAML files
├── pending/              # Processor tasks as markdown (human-readable)
│   ├── 001-respond-31.md
│   └── 002-respond-16.md
└── MANIFEST.md
```

### Pending File Format

```markdown
---
task_id: proc-31-abc123
github_issue: 31
repo: markster-exec/project-tracker
action_type: github_comment
entity: mark-de-grasse
status: pending
---

# Respond to #31: close or keep open?

## Context

**Entity:** Mark De Grasse / AI Branding Academy
**Workstream:** Email infrastructure setup
**Ticket:** [#31](https://github.com/markster-exec/project-tracker/issues/31)

## Question

Attila asked: "Close this task for the time being? or keep it open until we can add all mailboxes?"

## Draft Response

Keep it open - we'll add the remaining mailboxes once we increase the MailReef limit or clean up unused accounts.

## Decision

- [ ] approve
- [ ] approve with edits (modify draft above)
- [ ] reject
- [ ] convert to manual task
```

### Outbox Format (ivan-os writes)

```
ivan-os/data/sync/outbox/
└── decisions.json
```

```json
[
  {
    "task_id": "proc-31-abc123",
    "decision": "approve_edited",
    "edited_body": "Keep it open. We'll add remaining mailboxes once we clean up unused accounts on MailReef."
  },
  {
    "task_id": "proc-16-def456",
    "decision": "reject"
  }
]
```

### ivan import

```bash
ivan import [path]
```

- Reads `outbox/decisions.json`
- Updates processor tasks with decisions
- Approved → ready for `ivan done`
- Rejected → marked as skipped
- "Imported 2 decisions: 1 approved (edited), 1 rejected"

## Workflows

### Online Workflow

```bash
ivan sync                    # Get latest from sources
ivan process                 # Analyze tickets, create tasks
ivan next                    # Shows highest priority (may be processor task)
# Review draft
ivan done                    # Posts to GitHub
# Repeat
```

### Offline Workflow

```bash
# Before going offline
ivan sync
ivan process
ivan export

# Offline - work in ivan-os
# Review pending/, make decisions, write to outbox/

# Back online
ivan import
ivan next                    # Shows tasks with decisions applied
ivan done                    # Posts to GitHub
```

## Implementation Plan

### Phase 1: Core Processor

1. Add `action` field to Task model (migration)
2. Create `processor.py` module
3. Add `/process` endpoint
4. Add `ivan process` CLI command

### Phase 2: Execution

1. Add `post_comment()` to GitHubWriter
2. Modify `/done` endpoint to execute actions
3. Modify `ivan done` to show action preview

### Phase 3: Offline Support

1. Extend exporter to create `pending/` directory
2. Create importer for `outbox/decisions.json`
3. Add `ivan import` CLI command

### Phase 4: ivan-os Integration

1. ivan-os reads pending/ files
2. ivan-os presents review UI
3. ivan-os writes decisions to outbox/

## Files to Create/Modify

| File | Change |
|------|--------|
| `backend/app/models.py` | Add `action` JSON field, `linked_task_id` |
| `backend/app/processor.py` | **New** - ticket processing logic |
| `backend/app/writers/github.py` | Add `post_comment()` method |
| `backend/app/exporter.py` | Add `pending/` markdown export |
| `backend/app/importer.py` | **New** - import decisions from outbox |
| `backend/app/main.py` | Add `/process`, `/import` endpoints |
| `cli/ivan/__init__.py` | Add `process`, `import` commands; modify `done` |
| `alembic/versions/xxx_add_action.py` | Migration for action field |

## Future: Autonomous Mode

Current design has approval gate before posting. For autonomous mode:

```
Now:    Agent works → You approve → Posts to GitHub
Future: Agent works → Posts to GitHub → You review (can override)
```

The `action` field and execution logic stay the same. The change is:
- Remove approval gate (skip `ivan next` review)
- Add notification after posting
- Add `ivan undo` for reversing actions

## Key Decisions

1. **Processor tasks ARE tasks** - No separate queue, flows through existing system
2. **ClickUp Agent Queue for manual work** - List 901215555715 in VEZÉR space
3. **ivan-os is the offline system** - Export/import interface, not parallel mechanism
4. **Entity context informs responses** - Not generic drafts
5. **Approval before posting (for now)** - Architecture supports removing gate later
