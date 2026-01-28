---
id: ivan-task-manager-phase-4-roadmap
title: Ivan Task Manager - Phase 4 Roadmap
type: project
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [roadmap, phase-4, entity-awareness, bidirectional-sync, slack]
---

# Phase 4 Roadmap: From Working to Useful

## Executive Summary

Phase 0-3 built a working task aggregator. Phase 4 makes it actually useful by solving three critical gaps:

1. **Bot doesn't work for real use** — No links, no threading, can't have conversations
2. **Tasks lack context** — No entity/project awareness, AI produces "good sounding nonsense"
3. **One-way only** — Can't write back to sources, can't acknowledge completions

This document maps the full Phase 4 implementation across 5 sprints with clear dependencies.

---

## Current Pain Points

| Problem | Impact | Root Cause |
|---------|--------|------------|
| Bot messages have no links | Attila can't click to see task | `notifier.py` doesn't include URLs |
| Can't reply to bot | DM workarounds needed | Bot doesn't handle thread replies |
| "Mark" task has no Mark context | Wrong prioritization, confusing output | No entity registry |
| Tasks show "No deadline" | Miss project deadlines | No project-level deadline inheritance |
| Can't mark done in Slack | Must use CLI or source system | No bidirectional sync |
| Can't send docs to process | Manual task creation | No file handling |

---

## Dependency Graph

```
                    ┌─────────────────────┐
                    │  4A: Bot Comms Fix  │  ← START HERE (urgent, independent)
                    │    (~0.5 sprint)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  4B: Entity         │  ← FOUNDATION (everything needs this)
                    │  Awareness          │
                    │    (~1 sprint)      │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                                 ▼
┌─────────────────────┐              ┌─────────────────────┐
│  4C: Bidirectional  │              │  4D: Rich Slack     │
│  Sync               │              │  Input              │
│    (~1 sprint)      │              │    (~1 sprint)      │
└─────────────────────┘              └──────────┬──────────┘
                                                │
                                                ▼
                                     ┌─────────────────────┐
                                     │  4E: Image/Screen   │
                                     │  Processing         │
                                     │    (~1 sprint)      │
                                     └─────────────────────┘
```

**Linear execution order:** 4A → 4B → 4C → 4D → 4E

---

## Sprint 4A: Bot Communication Fix

**Goal:** Make the Slack bot actually usable for real conversations.

**Duration:** ~0.5 sprint (2-3 days)

**Dependencies:** None (can start immediately)

**Blocks:** Everything else (unusable bot = unusable system)

### Problems Solved

1. Messages don't include task links → Attila can't see what we're talking about
2. Bot ignores thread replies → Forces DM workarounds
3. Message formatting is plain → Hard to scan
4. No confirmation of actions → Unclear if command worked

### Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Task links in all messages | Every task mention includes clickable URL |
| 2 | Thread reply handling | Bot responds in-thread when mentioned in thread |
| 3 | Rich message formatting | Blocks, buttons, structured layout |
| 4 | Action confirmations | Clear feedback: "✓ Marked complete: [Task Name](url)" |
| 5 | Error messages with guidance | "Task not found. Try `tasks` to see your list." |

### Technical Changes

```
backend/app/bot.py
├── Add thread_ts handling for replies
├── Use Slack Block Kit for rich formatting
└── Include task.url in all task-related messages

backend/app/notifier.py
├── Update send_message() to use blocks
├── Add task URL to all notifications
└── Support thread replies
```

### Acceptance Criteria

- [ ] Every task notification includes clickable link to source (ClickUp/GitHub)
- [ ] Replying to a bot message in a thread gets a response in that thread
- [ ] `next` command shows task with link, score breakdown, and context
- [ ] `done` command confirms with task name and link
- [ ] Another person can interact with the bot (not just Ivan)

### Commits (planned)

1. `feat(bot): add task URLs to all messages`
2. `feat(bot): handle thread replies with thread_ts`
3. `feat(notifier): use Slack Block Kit for rich formatting`
4. `test(bot): add tests for thread handling and formatting`
5. `docs: update slack integration with new message format`

---

## Sprint 4B: Entity Awareness

**Goal:** Tasks know their context (who, what project, why it matters).

**Duration:** ~1 sprint (1 week)

**Dependencies:** 4A complete (need working bot to show entity context)

**Blocks:** 4C, 4D (bidirectional sync and rich input need entity resolution)

### Problems Solved

1. Tasks exist in isolation → No project context
2. "No deadline" when project has deadline → Missed commitments
3. AI lacks context → "Good sounding nonsense" outputs
4. Can't answer "What's happening with Mark?" → No entity view

### Core Concepts

**Entity:** A person or company Ivan has a relationship with.

```yaml
# entities/mark-smith-ai-branding.yaml
id: mark-smith-ai-branding
type: person
name: Mark Smith
company: AI Branding Academy
email: mark@example.com

intention: "Showcase client → Channel partner → Revenue multiplier"

workstreams:
  - id: mark-system-setup
    name: System Setup on Markster
    status: active
    deadline: 2026-01-25

  - id: mark-workshop
    name: Workshop Success
    status: planned
    deadline: 2026-02-15
    revenue_potential: "$10,000+"

channels:
  github: "markster-exec/project-tracker#16"
  clickup: "869bxxuwr"
  gdoc: "1byTVcZUJ7RXSOWTlYhJ7pQiARarBNNUB_adjXIuSnv8"

context_summary: |
  Mark is building AI Branding Academy. We're setting up his system
  on Markster as a showcase. Success here = case study + channel partner.
  Workshop in mid-Feb is the key milestone.
```

**Task-Entity Mapping:**
- GitHub: Parse `[CLIENT:Mark]` from issue title
- ClickUp: Use tags (`client:mark`) or custom field
- Manual: Mapping file for edge cases

### Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Entity registry | YAML files in `entities/` directory |
| 2 | Entity model | SQLAlchemy model for caching entity data |
| 3 | Task-entity mapping | Parse entity from task titles/tags |
| 4 | Project deadline inheritance | Tasks inherit deadline from workstream |
| 5 | Enhanced scorer | Include project urgency, entity priority |
| 6 | Context display | `ivan next` shows entity context |
| 7 | Entity CLI commands | `ivan entity mark`, `ivan projects` |

### Technical Changes

```
entities/                          # NEW: Entity YAML files
├── mark-smith-ai-branding.yaml
├── kyle-stearns-ace-industrial.yaml
└── ...

backend/app/
├── models.py                      # Add Entity, Workstream models
├── entity_loader.py               # NEW: Load entities from YAML
├── entity_mapper.py               # NEW: Map tasks to entities
├── scorer.py                      # Update scoring with entity context
└── main.py                        # Add entity endpoints

cli/ivan/
└── __init__.py                    # Add entity commands
```

### Enhanced Scoring

```python
# Current scoring
Score = (Revenue × 1000) + (Blocking × 500 × count) + (Urgency × 100) + Recency

# Enhanced scoring (with entity awareness)
Score = (Revenue × 1000)
      + (Blocking × 500 × count)
      + (Task Urgency × 100)        # Task's own deadline
      + (Project Urgency × 50)      # Workstream deadline
      + (Entity Priority × 25)      # How important is this relationship
      + (Recency × 1)
```

### Acceptance Criteria

- [ ] Can create entity YAML file and system loads it
- [ ] Tasks with `[CLIENT:Mark]` in title are linked to Mark entity
- [ ] Task without deadline but in workstream with deadline shows workstream deadline
- [ ] `ivan next` shows: entity name, workstream, why urgent
- [ ] `ivan entity mark` shows all tasks/workstreams for Mark
- [ ] Scoring reflects project urgency (task in overdue workstream ranks higher)

### Commits (planned)

1. `feat(models): add Entity and Workstream models`
2. `feat(entity): add YAML entity loader`
3. `feat(entity): add task-entity mapping from titles/tags`
4. `feat(scorer): add project urgency and entity priority`
5. `feat(cli): add entity and projects commands`
6. `feat(bot): show entity context in task messages`
7. `docs: add entity schema and examples`
8. `test(entity): add entity loader and mapper tests`

---

## Sprint 4C: Bidirectional Sync

**Goal:** Write back to ClickUp/GitHub (complete tasks, add comments).

**Duration:** ~1 sprint (1 week)

**Dependencies:** 4A (bot works), 4B (entity awareness for routing)

**Blocks:** None directly, but enables real workflow

### Problems Solved

1. Can't mark done via Slack → Must switch to source system
2. Comments not synced → Context lost between systems
3. External changes not detected → Stale data
4. No way to create tasks via Slack → Manual creation only

### Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | ClickUp writer | Complete task, add comment, create task |
| 2 | GitHub writer | Close issue, add comment, create issue |
| 3 | Unified write API | `POST /tasks/{id}/complete`, `POST /tasks/{id}/comment` |
| 4 | Webhook receivers | Real-time updates from ClickUp/GitHub |
| 5 | Conflict resolution | Handle simultaneous updates gracefully |
| 6 | Slack commands | "done 17", "comment on current: notes here" |

### Technical Changes

```
backend/app/
├── clickup_writer.py              # NEW: Write to ClickUp API
├── github_writer.py               # NEW: Write to GitHub API
├── webhooks.py                    # NEW: Webhook receivers
└── main.py                        # Add write endpoints, webhook routes

Webhook endpoints:
├── POST /webhooks/clickup         # ClickUp task events
└── POST /webhooks/github          # GitHub issue events
```

### API Additions

```
POST /tasks/{id}/complete          # Mark task done in source
POST /tasks/{id}/comment           # Add comment to source
POST /tasks                        # Create task (routes to appropriate source)
POST /webhooks/clickup             # Receive ClickUp webhooks
POST /webhooks/github              # Receive GitHub webhooks
```

### Webhook Events

| Source | Event | Action |
|--------|-------|--------|
| ClickUp | `taskStatusUpdated` | Update local status |
| ClickUp | `taskCommentPosted` | Store comment, update last_activity |
| GitHub | `issues.closed` | Mark local task complete |
| GitHub | `issue_comment.created` | Store comment, update last_activity |

### Acceptance Criteria

- [ ] `ivan done` marks task complete in source system (ClickUp or GitHub)
- [ ] "done" in Slack marks current task complete in source
- [ ] `ivan comment "notes"` adds comment to current task in source
- [ ] External task completion (in ClickUp/GitHub) syncs within 1 minute via webhook
- [ ] Conflict: external change + local change = external wins, user notified

### Commits (planned)

1. `feat(writer): add ClickUp task writer (complete, comment, create)`
2. `feat(writer): add GitHub issue writer (close, comment, create)`
3. `feat(api): add task write endpoints`
4. `feat(webhooks): add ClickUp webhook receiver`
5. `feat(webhooks): add GitHub webhook receiver`
6. `feat(bot): add comment command`
7. `feat(cli): update done command to write back`
8. `test(writer): add writer tests with mocked APIs`
9. `docs: add webhook setup instructions`

---

## Sprint 4D: Rich Slack Input

**Goal:** Handle files, documents, and forwards in Slack.

**Duration:** ~1 sprint (1 week)

**Dependencies:** 4A (bot infrastructure), 4B (entity resolution for routing)

**Blocks:** 4E (image processing builds on file handling)

### Problems Solved

1. Can't send docs to process → Manual task extraction
2. Forwarded messages ignored → Lost context
3. No file handling → Can't share attachments
4. Can't route content to entities → No context linkage

### Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | File upload handling | Detect and download Slack file uploads |
| 2 | PDF text extraction | Extract text from PDF attachments |
| 3 | Document parsing | Extract action items, deadlines, mentions |
| 4 | Entity mention resolution | "Send this to Mark" → routes to Mark entity |
| 5 | Forward processing | Handle forwarded messages/emails |
| 6 | Task creation from content | "Create task from this" → extracts and creates |

### Technical Changes

```
backend/app/
├── file_processor.py              # NEW: Handle file downloads and processing
├── document_parser.py             # NEW: Extract text, action items
├── entity_resolver.py             # NEW: Resolve mentions to entities
└── bot.py                         # Update to handle file events

Dependencies:
├── pymupdf                        # PDF text extraction
├── python-docx                    # Word document extraction
└── (Azure Document Intelligence)  # Optional: better extraction
```

### Processing Pipeline

```python
async def handle_slack_file(event):
    # 1. Download file from Slack
    file_content = await download_slack_file(event["file"])

    # 2. Extract text based on type
    if file_type == "pdf":
        text = extract_pdf_text(file_content)
    elif file_type == "docx":
        text = extract_docx_text(file_content)
    else:
        text = file_content.decode()

    # 3. Parse for actionable content
    parsed = await parse_document(text)
    # Returns: { action_items: [], deadlines: [], mentions: [] }

    # 4. Resolve entity mentions
    entities = await resolve_entities(parsed["mentions"])

    # 5. Ask user what to do
    await send_options(user_id, parsed, entities)
```

### Acceptance Criteria

- [ ] Upload PDF to Slack DM → Bot extracts text and shows summary
- [ ] "Create tasks from this" on a doc → Extracts action items as tasks
- [ ] "Send to Mark" on any content → Links to Mark entity
- [ ] Forward an email screenshot → Bot acknowledges and offers to create task
- [ ] Uploaded doc with deadlines → Bot highlights them

### Commits (planned)

1. `feat(bot): handle Slack file upload events`
2. `feat(processor): add PDF text extraction with pymupdf`
3. `feat(processor): add document parsing for action items`
4. `feat(resolver): add entity mention resolution`
5. `feat(bot): add "create task from this" command`
6. `feat(bot): add forward message handling`
7. `test(processor): add document processing tests`
8. `docs: add file handling documentation`

---

## Sprint 4E: Image/Screenshot Processing

**Goal:** Process images and screenshots with Azure Vision.

**Duration:** ~1 sprint (1 week)

**Dependencies:** 4D (file handling infrastructure)

**Blocks:** None (final sprint in Phase 4)

**Note:** Separated from 4D due to Azure complexity and potential API issues.

### Problems Solved

1. Can't process screenshots → Manual transcription
2. No OCR for images → Text in images lost
3. Can't describe visual content → Context missing
4. No UI element recognition → Can't understand app screenshots

### Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | Azure Vision integration | Connect to Azure Computer Vision API |
| 2 | OCR for images | Extract text from screenshots |
| 3 | Image description | AI-generated description of image content |
| 4 | UI element recognition | Identify buttons, forms, errors in app screenshots |
| 5 | Fallback handling | Graceful degradation if Azure unavailable |

### Technical Changes

```
backend/app/
├── vision_processor.py            # NEW: Azure Vision API integration
├── file_processor.py              # Update to route images to vision
└── config.py                      # Add Azure Vision credentials

Environment:
├── AZURE_VISION_ENDPOINT
├── AZURE_VISION_KEY
└── VISION_ENABLED=true/false      # Feature flag for gradual rollout
```

### Azure Vision Capabilities

| Capability | Use Case |
|------------|----------|
| OCR | Extract text from screenshots, photos of documents |
| Image Analysis | Describe what's in the image |
| Object Detection | Identify UI elements, people, objects |

### Acceptance Criteria

- [ ] Upload screenshot → Bot extracts all visible text via OCR
- [ ] Upload image → Bot provides description of contents
- [ ] App screenshot with error → Bot identifies error message
- [ ] Azure unavailable → Bot responds "Image processing unavailable, please describe"
- [ ] Cost tracking → Log API calls for budget monitoring

### Commits (planned)

1. `feat(vision): add Azure Vision API client`
2. `feat(vision): add OCR text extraction`
3. `feat(vision): add image description`
4. `feat(processor): route images to vision processor`
5. `feat(config): add vision feature flag and cost tracking`
6. `test(vision): add vision processor tests with mocked API`
7. `docs: add Azure Vision setup instructions`

---

## GitHub Issues

Issues tracked in this repo (`markster-exec/ivan-task-manager`):

| Issue | Title |
|-------|-------|
| #1 | Phase 4A: Bot Communication Fix |
| #2 | Phase 4B: Entity Awareness |
| #3 | Phase 4C: Bidirectional Sync |
| #4 | Phase 4D: Rich Slack Input |
| #5 | Phase 4E: Image/Screenshot Processing |

---

## Success Metrics

After Phase 4 completion:

| Metric | Before | After |
|--------|--------|-------|
| Bot usability | Broken (no links, no threads) | Fully conversational |
| Task context | None | Entity + project + why |
| Sync direction | Read-only | Bidirectional |
| Input types | Text commands only | Text, files, images |
| Entity queries | Not possible | "What's happening with Mark?" |

---

## Timeline

| Sprint | Focus | Duration | Cumulative |
|--------|-------|----------|------------|
| 4A | Bot Communication Fix | 0.5 week | 0.5 weeks |
| 4B | Entity Awareness | 1 week | 1.5 weeks |
| 4C | Bidirectional Sync | 1 week | 2.5 weeks |
| 4D | Rich Slack Input | 1 week | 3.5 weeks |
| 4E | Image/Screenshot | 1 week | 4.5 weeks |

**Total:** ~4.5 weeks for full Phase 4

---

## How to Use This Document

**Starting a sprint:**
1. Read this document for context
2. Read the specific sprint section
3. Create/find the GitHub issue
4. Implement following the commit plan
5. Update CHANGELOG

**Context lost between sessions:**
1. Read SESSION_STATE.md for current state
2. Read this document for full roadmap
3. Check GitHub issues for progress
4. Continue from last commit

**Changing priorities:**
1. Update this document with new order
2. Update GitHub issue priorities
3. Note reasoning in commit message

---

## Appendix: Entity Schema Reference

Full entity YAML schema for reference:

```yaml
# Required fields
id: string                    # Unique identifier (slug format)
type: person | company        # Entity type
name: string                  # Display name

# Optional identity
company: string               # Company name (for person type)
email: string                 # Primary email
linkedin: string              # LinkedIn URL
phone: string                 # Phone number

# Relationship context
intention: string             # What we're trying to achieve
relationship_type: client | prospect | partner | investor | team | vendor | network

# Workstreams (projects/initiatives)
workstreams:
  - id: string                # Unique within entity
    name: string              # Display name
    status: planned | active | blocked | complete
    deadline: date            # Hard deadline (optional)
    milestone: string         # What the deadline represents
    revenue_potential: string # Expected value (optional)
    depends_on: [string]      # Other workstream IDs

# Cross-references to other systems
channels:
  github: string              # Issue/PR reference
  clickup: string             # Task ID
  gdoc: string                # Document ID
  slack: string               # Channel name
  email_threads: [string]     # Thread IDs

# Context
context_summary: string       # 2-3 sentence summary
last_touch: date              # Last interaction
next_action: string           # What needs to happen next

# Contacts (for company entities)
contacts:
  - name: string
    role: string
    email: string
```

---

*Last updated: 2026-01-28*
*Next review: After each sprint completion*
