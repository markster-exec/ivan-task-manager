# Ivan Task Manager - Design Document

**Date:** 2026-01-27
**Status:** Approved
**Owner:** Ivan Ivanka

---

## Overview

A unified task management system that aggregates tasks from ClickUp, GitHub, and Slack, provides intelligent prioritization, and delivers actionable notifications. Designed for a sales-focused workflow where revenue and unblocking others take priority.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         RAILWAY (24/7)                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Ivan Task Manager                       │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐   │  │
│  │  │ Syncer  │  │ Scorer  │  │ Notifier│  │   API       │   │  │
│  │  │ (hourly)│  │ (Azure) │  │ (Slack) │  │  (FastAPI)  │   │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘   │  │
│  │       │            │            │              │           │  │
│  │       └────────────┴────────────┴──────────────┘           │  │
│  │                         │                                   │  │
│  │                    ┌────┴────┐                              │  │
│  │                    │  Cache  │  (SQLite/PostgreSQL)         │  │
│  │                    └─────────┘                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        ▲           ▲           ▲                    ▲
        │           │           │                    │
   ┌────┴────┐ ┌────┴────┐ ┌────┴────┐         ┌────┴────┐
   │ ClickUp │ │ GitHub  │ │  Slack  │         │  ivan   │
   │   API   │ │   API   │ │   API   │         │   CLI   │
   └─────────┘ └─────────┘ └─────────┘         └─────────┘
```

**Components:**
- **Syncer** — Pulls tasks hourly from ClickUp + GitHub, caches locally
- **Scorer** — Uses Azure OpenAI (GPT 5.2) to prioritize tasks
- **Notifier** — Sends Slack DMs (instant for urgent, hourly digest for rest)
- **API** — FastAPI endpoint for CLI and Slack bot queries
- **Cache** — SQLite for dev, PostgreSQL for production

## Data Model

```python
class Task:
    id: str                    # "clickup:869bxxud4" or "github:17"
    source: str                # "clickup" | "github"
    title: str
    description: str
    status: str                # normalized: "todo" | "in_progress" | "done"
    assignee: str              # "ivan" | "tamas" | "attila"
    due_date: date | None

    # Scoring inputs
    is_revenue: bool           # True if linked to HubSpot deal (or tagged)
    is_blocking: list[str]     # ["tamas", "attila"] if blocking someone
    blocked_by: list[str]      # Task IDs this is blocked by

    # Metadata
    url: str                   # Direct link to task
    last_activity: datetime    # Last comment/update
    source_data: dict          # Raw API response for debugging
```

## Scoring Algorithm

```
Score = (Revenue × 1000) + (Blocking × 500) + (Urgency × 100) + Recency

Where:
- Revenue:  1 if is_revenue else 0
- Blocking: count of people blocked (×500 each)
- Urgency:  5 if overdue, 4 if due today, 3 if due this week, 1 otherwise
- Recency:  1 if activity in last 24h else 0
```

**Priority order:** Revenue first → Blocking others → Due date

**Example scores:**

| Task | Revenue | Blocking | Urgency | Score |
|------|---------|----------|---------|-------|
| Kyle deal (overdue, revenue) | 1000 | 0 | 500 | **1500** |
| Tamás + Attila waiting | 0 | 1000 | 300 | **1300** |
| Tamás waiting, due today | 0 | 500 | 400 | **900** |
| Blog post (due Friday) | 0 | 0 | 300 | **300** |

## Blocking Detection

- **ClickUp:** Native task dependencies API
- **GitHub:** Parse "Blocked by #X" or "Blocks #Y" from issue bodies during sync
- **Slack:** Not scanned (too expensive, unreliable)

## Notifications

**Instant** (Slack DM immediately):
- Task score ≥ 1000 (revenue or blocking 2+ people)
- Task becomes overdue
- Someone comments mentioning you on a high-score task
- Blocker resolved (task you were waiting on is done)

**Hourly digest** (batched):
- New tasks assigned to you
- Tasks where due date is approaching (tomorrow)
- Comments on your tasks
- Status changes

**Morning briefing** (7am Slack DM):
```
☀️ Good morning, Ivan

🔥 TOP 3 FOCUS
1. [Kyle deal] Present offer at LA meeting (Score: 1500)
   → Overdue, revenue. Attila pinged for pricing help.
   🔗 https://github.com/markster-exec/project-tracker/issues/8

2. [Mark handoff] Hand off case study to Attila (Score: 900)
   → Blocking Attila. Due today.
   🔗 https://app.clickup.com/t/869bxxuwr

3. [Outbound] Send 200 manual messages (Score: 400)
   → Due today.
   🔗 https://app.clickup.com/t/869bxxuyt

📊 SUMMARY
• 4 tasks overdue
• 3 tasks due today
• 2 people waiting on you (Attila, Tamás)

💬 UNREAD
• Attila commented on Kyle brief (GitHub #8)
• Tamás completed "Launch accountant campaign"

Type `ivan next` to start working.
```

**Quiet hours:** No notifications 10pm - 7am (configurable)

## Interfaces

### Terminal CLI (`ivan`)

```bash
ivan next              # Show #1 priority with link + context
ivan done              # Complete current, show next
ivan skip              # Move to next without completing
ivan block "reason"    # Mark blocked, notify blocker, show next
ivan morning           # Morning briefing
ivan tasks             # All tasks sorted by score
ivan sync              # Force refresh from all sources
ivan blocked           # Tasks you're waiting on
ivan blocking          # People waiting on you
```

### Slack Bot (DM or @mention)

Natural language interface:

```
You: next
Bot: → [Mark handoff] Hand off case study to Attila
     🔗 https://app.clickup.com/t/869bxxuwr

You: done, moving on
Bot: ✓ Marked complete. Next up:
     → [Outbound] Send 200 manual messages

You: skip this for now, I need to prep for Kyle call
Bot: ✓ Skipped. Showing Kyle-related tasks:
     → [Kyle deal] Present offer at LA meeting

You: [drops PDF] here's Kyle's company info, save this to the brief
Bot: ✓ Uploaded to Google Drive, linked in GitHub issue #8

You: block this, waiting on Attila for pricing
Bot: ✓ Marked blocked. Notified Attila.
     → Next: [Investor pipeline] Maintain 10 conversations
```

## State Management

Railway service maintains state:
- Current task being worked on
- Task cache from all sources
- Notification history

Two ways to mark tasks done:
1. Via CLI/Slack (`ivan done`) — immediately updates ClickUp/GitHub
2. Directly in ClickUp/GitHub — picked up on next sync (hourly or `ivan sync`)

## Tech Stack

Following Markster Development Standards:
- **Backend:** Python 3, FastAPI, SQLAlchemy, Alembic
- **Database:** SQLite (dev), PostgreSQL (production)
- **AI:** Azure OpenAI (GPT 5.2) — uses Azure credits, not Claude
- **Deployment:** Docker containers on Railway
- **CI/CD:** GitHub Actions

## Repository Structure

```
ivan-task-manager/
├── AGENTS.md
├── README.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── syncer.py        # ClickUp/GitHub sync
│   │   ├── scorer.py        # Prioritization logic
│   │   ├── notifier.py      # Slack notifications
│   │   └── models.py        # SQLAlchemy models
│   ├── tests/
│   └── alembic/
├── cli/
│   └── ivan.py              # CLI client
├── docs/
│   ├── index.md
│   ├── architecture/
│   ├── setup/
│   ├── plans/
│   └── runbooks/
├── scripts/
└── .github/workflows/
```

## Implementation Phases

**Phase 1: Core (Week 1)**
- Railway FastAPI service
- ClickUp + GitHub syncers
- SQLite cache
- Scoring algorithm
- `ivan` CLI with `next`, `done`, `tasks`, `sync`

**Phase 2: Slack Bot (Week 2)**
- Slack bot responding to DMs
- Natural language via Azure OpenAI
- Morning briefing (scheduled)
- Instant + digest notifications

**Phase 3: Polish (Week 3)**
- `skip`, `block`, `blocking`, `blocked` commands
- File drops in Slack → Drive upload
- Quiet hours
- Error handling + tests

## Future Integrations

- **HubSpot:** Deals, contacts, sales tasks — auto-prioritize revenue
- **Calendar:** Meeting prep, availability context
- **Email:** Search historical threads for context

## Configuration

Stored in `~/.markstercli/config.json` (via markster-cli):

```json
{
  "ivan": {
    "clickup_list_id": "901215490741",
    "github_repo": "markster-exec/project-tracker",
    "slack_user_id": "U084S552VRD",
    "morning_briefing_time": "07:00",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "07:00",
    "azure_endpoint": "https://ai-devteam-resource.cognitiveservices.azure.com"
  }
}
```

## Key IDs

**ClickUp:**
- Workspace: 9012270250 (Markster)
- List: 901215490741 (Mesterlista2026)
- Ivan: 54476784
- Tamás: 2695145
- Attila: 81842673

**GitHub:**
- Repo: markster-exec/project-tracker
- Ivan: ivanivanka
- Attila: atiti

**Slack:**
- Workspace: T085KBJ74N5 (Markster)
- Ivan: U084S552VRD
- Tamás: U0853TD9VFF
- Attila: U0856NMSALA

---

*Design approved: 2026-01-27*
