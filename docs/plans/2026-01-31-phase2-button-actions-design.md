---
id: phase2-button-actions-design
title: Phase 2 - Button Actions Design
type: plan
status: active
owner: ivan
created: 2026-01-31
updated: 2026-01-31
tags: [slack-bot, phase-2, interactive]
---

# Phase 2: Button Actions Design

## Overview

Make escalation message buttons functional. Users can defer, complete, snooze, or delegate tasks directly from Slack without switching apps.

## Deliverables

1. **Defer button** — Update due date in source system
2. **Done button** — Modal flow to mark complete with context
3. **Snooze button** — Hide locally without changing source
4. **Delegate button** — Reassign to team member

## Architecture

### No New Endpoint Needed

Socket Mode handles both events and interactive components through the same WebSocket connection. Action handlers are registered directly on the Bolt app.

### File Changes

| File | Change |
|------|--------|
| `backend/app/slack_actions.py` | **NEW** — All action/view handlers |
| `backend/app/bot.py` | Import and register handlers from slack_actions |
| `backend/app/slack_blocks.py` | Replace placeholder buttons with real interactive elements |
| `backend/app/models.py` | Add `snooze_until` column to Task |
| `backend/app/writers/base.py` | Add `update_due_date()` and `reassign()` abstract methods |
| `backend/app/writers/clickup.py` | Implement new methods |
| `backend/app/writers/github.py` | Implement new methods (with limitations) |
| `backend/app/config.py` | Add team member ID mappings |

### Action Flow

```
User clicks [Defer] button
    ↓
Slack sends interaction payload via Socket Mode
    ↓
bolt_app.action("defer_button") handler fires
    ↓
Handler opens dropdown (overflow menu or modal)
    ↓
User selects "3 days"
    ↓
bolt_app.action("defer_select") handler fires
    ↓
Handler calls writer.update_due_date()
    ↓
Handler updates local DB
    ↓
Handler updates original message to show confirmation
```

## Button Designs

### 1. Defer Button

**Interaction:** Button → Dropdown menu (static_select in modal)

**Options:**
- Tomorrow
- 3 days
- 1 week
- Pick date (opens date picker)

**Action:**
1. Calculate new due date
2. Call `writer.update_due_date(source_id, new_date)`
3. Update `Task.due_date` in local DB
4. Reset `Task.escalation_level` to 0
5. Update message: "✓ Deferred to {date}"

**GitHub limitation:** GitHub issues don't have due dates. For GitHub tasks:
- Add comment: "Due date updated to {date}"
- Update local DB only

### 2. Done Button

**Interaction:** Button → Modal with text input

**Modal fields:**
- Text input: "What happened?" (optional, 500 char max)

**Action:**
1. Get context text from modal
2. If context provided, call `writer.comment(source_id, context)`
3. Call `writer.complete(source_id)`
4. Update `Task.status = "done"` in local DB
5. Update message: "✓ Completed"

### 3. Snooze Button

**Interaction:** Button → Dropdown menu

**Options:**
- 1 day
- 3 days
- 1 week

**Action:**
1. Calculate snooze_until datetime
2. Update `Task.snooze_until` in local DB
3. Update message: "💤 Snoozed until {date}"

**Note:** Snooze is LOCAL ONLY. Does not touch source system.

### 4. Delegate Button

**Interaction:** Button → Dropdown menu

**Options:**
- Attila
- Tamas

**Action:**
1. Map name to source system username
2. Call `writer.reassign(source_id, username)`
3. Update `Task.assignee` in local DB
4. Update message: "→ Delegated to {name}"

**Team mapping (add to config):**
```python
TEAM_MEMBERS = {
    "attila": {
        "clickup_id": "81842673",
        "github_username": "atiti",
    },
    "tamas": {
        "clickup_id": "2695145",
        "github_username": None,  # Not a GitHub collaborator
    },
}
```

## Database Changes

### Task Model

Add column:
```python
snooze_until = Column(DateTime, nullable=True)
```

Migration:
```python
# alembic/versions/002_add_snooze_until.py
op.add_column('tasks', sa.Column('snooze_until', sa.DateTime(), nullable=True))
```

## Writer Interface Changes

### base.py

```python
@abstractmethod
async def update_due_date(self, source_id: str, new_date: date) -> WriteResult:
    """Update task due date in source system."""
    pass

@abstractmethod
async def reassign(self, source_id: str, assignee_id: str) -> WriteResult:
    """Reassign task to another user in source system."""
    pass
```

### clickup.py

```python
async def update_due_date(self, source_id: str, new_date: date) -> WriteResult:
    # PUT /task/{source_id} with {"due_date": timestamp_ms}

async def reassign(self, source_id: str, assignee_id: str) -> WriteResult:
    # PUT /task/{source_id} with {"assignees": {"add": [assignee_id]}}
```

### github.py

```python
async def update_due_date(self, source_id: str, new_date: date) -> WriteResult:
    # GitHub issues don't have due dates
    # Add comment instead: "Due date updated to {date}"
    return await self.comment(source_id, f"📅 Due date updated to {new_date}")

async def reassign(self, source_id: str, assignee_username: str) -> WriteResult:
    # PATCH /repos/{repo}/issues/{source_id} with {"assignees": [username]}
```

## Slack Block Kit Updates

### Replace Placeholder Buttons

Current (Phase 1):
```python
def action_buttons_placeholder(task_id: str) -> dict:
    # Buttons with action_id="defer_placeholder" etc.
```

New (Phase 2):
```python
def action_buttons(task_id: str) -> dict:
    return {
        "type": "actions",
        "block_id": f"actions_{task_id}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Defer"},
                "value": task_id,
                "action_id": "defer_button",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Done"},
                "value": task_id,
                "action_id": "done_button",
                "style": "primary",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Snooze"},
                "value": task_id,
                "action_id": "snooze_button",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Delegate"},
                "value": task_id,
                "action_id": "delegate_button",
            },
        ],
    }
```

## Action Handlers (slack_actions.py)

```python
# Defer button → opens modal with dropdown
@bolt_app.action("defer_button")
async def handle_defer_button(ack, body, client):
    await ack()
    task_id = body["actions"][0]["value"]
    # Open modal with defer options

@bolt_app.view("defer_modal")
async def handle_defer_submit(ack, body, client, view):
    await ack()
    # Process defer selection

# Done button → opens modal with text input
@bolt_app.action("done_button")
async def handle_done_button(ack, body, client):
    await ack()
    task_id = body["actions"][0]["value"]
    # Open completion modal

@bolt_app.view("done_modal")
async def handle_done_submit(ack, body, client, view):
    await ack()
    # Complete task with context

# Snooze button → opens modal with dropdown
@bolt_app.action("snooze_button")
async def handle_snooze_button(ack, body, client):
    await ack()
    # Open snooze modal

@bolt_app.view("snooze_modal")
async def handle_snooze_submit(ack, body, client, view):
    await ack()
    # Set snooze_until

# Delegate button → opens modal with dropdown
@bolt_app.action("delegate_button")
async def handle_delegate_button(ack, body, client):
    await ack()
    # Open delegate modal

@bolt_app.view("delegate_modal")
async def handle_delegate_submit(ack, body, client, view):
    await ack()
    # Reassign task
```

## Testing Strategy

1. **Unit tests** for each handler (mock Slack client)
2. **Integration tests** for writer methods (mock HTTP)
3. **Manual test** in Slack sandbox

## Success Criteria

- [ ] Defer updates due date in ClickUp
- [ ] Defer adds comment to GitHub (no native due date)
- [ ] Done collects context via modal, marks complete
- [ ] Snooze hides task locally (snooze_until column)
- [ ] Delegate reassigns in ClickUp
- [ ] Delegate reassigns in GitHub (if collaborator)
- [ ] All buttons update the original message with confirmation
- [ ] All tests pass

## Implementation Order

1. Add `snooze_until` column + migration
2. Add writer methods (`update_due_date`, `reassign`)
3. Update `slack_blocks.py` with real buttons
4. Create `slack_actions.py` with handlers
5. Register handlers in `bot.py`
6. Write tests
7. Manual test in Slack
