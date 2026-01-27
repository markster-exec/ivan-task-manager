# Ivan Task Manager - Design Document

**Date:** 2026-01-27
**Status:** Approved

## Problem Statement

Ivan uses multiple task systems (ClickUp with Tamás, GitHub with Attila) and needs a unified view that:
1. Shows the single most important task to work on
2. Prioritizes revenue-generating work
3. Surfaces blockers (people waiting on you)
4. Works with both Claude Code and Codex

## Design Decisions

### Interface

**Decision:** Both CLI (`ivan`) and Slack scheduled messages

- CLI for on-demand queries when at computer
- Slack for morning briefings and urgent alerts when on phone
- API backend enables both interfaces

### Prioritization Algorithm

```
Score = (Revenue × 1000) + (Blocking × 500 × count) + (Urgency × 100) + Recency
```

| Factor | Points | Rationale |
|--------|--------|-----------|
| Revenue | 1000 | Money-making work wins |
| Blocking | 500/person | Unblocking others multiplies output |
| Urgency (overdue) | 500 | Past due = critical |
| Urgency (today) | 400 | Due today = high |
| Urgency (this week) | 300 | Near deadline = medium |
| Urgency (future) | 100 | Has time = low |
| Recency | 1 | Tiebreaker for active tasks |

**Key insight:** Blocking 2+ people can outrank non-urgent revenue task.

### Revenue Identification

- ClickUp: Tasks with `revenue`, `deal`, or `client` tags
- GitHub: Labels containing `client`, `revenue`, or `deal`
- Future: HubSpot deal links

### Blocking Detection

- ClickUp: Dependencies API (native support)
- GitHub: Parse `Blocked by #X` and `Blocks #Y` from issue body

### Sync Frequency

**Decision:** Hourly continuous sync (24/7)

- Sales context: Time-sensitive, can't wait for next morning
- Token efficient: Cache in SQLite, only API calls for sync

### Deployment

**Decision:** Railway (cloud, 24/7)

- Uses existing Azure credits
- Docker containerized
- PostgreSQL in production, SQLite in dev

### AI Processing

**Decision:** Azure OpenAI (GPT 5.2) for future NLP features

- NOT using Claude tokens for this (cost efficiency)
- Initial version has no AI - pure deterministic scoring

### Notifications

**Decision:** Smart digest with instant alerts

| Notification Type | When | Timing |
|-------------------|------|--------|
| Instant | Score >= 1000 (urgent) | Immediately |
| Morning briefing | Daily | 07:00 |
| Hourly digest | New/updated tasks | Every hour |

Quiet hours: 22:00 - 07:00 (no non-morning notifications)

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   ClickUp   │     │   GitHub    │     │    Slack    │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────┬───────┘                   │
                   ▼                           │
         ┌─────────────────┐                   │
         │   Syncer        │                   │
         │   (hourly)      │                   │
         └────────┬────────┘                   │
                  ▼                            │
         ┌─────────────────┐                   │
         │   SQLite DB     │                   │
         │   (cache)       │                   │
         └────────┬────────┘                   │
                  ▼                            │
         ┌─────────────────┐                   │
         │   Scorer        │                   │
         │   (priority)    │                   │
         └────────┬────────┘                   │
                  │                            │
       ┌──────────┴──────────┐                 │
       ▼                     ▼                 ▼
┌─────────────┐     ┌─────────────┐   ┌─────────────┐
│  CLI (ivan) │     │  FastAPI    │   │  Notifier   │
└─────────────┘     └─────────────┘   └─────────────┘
```

## State Management

- Railway backend maintains "current task" state
- Both `ivan done` and direct ClickUp/GitHub completion work
- Next sync picks up external changes

## CLI Commands

```bash
ivan next      # Highest priority task with link
ivan done      # Mark complete, show next
ivan skip      # Skip, show next
ivan tasks     # All tasks sorted
ivan morning   # Morning briefing
ivan sync      # Force sync
ivan blocking  # Who's waiting on you
ivan blocked   # What you're waiting on (future)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tasks` | GET | All tasks sorted |
| `/next` | GET | Highest priority task |
| `/done` | POST | Mark current complete |
| `/skip` | POST | Skip current |
| `/sync` | POST | Force sync |
| `/morning` | GET | Morning briefing data |

## Future Enhancements

1. **Phase 2:** Slack bot for natural language queries
2. **Phase 3:** HubSpot integration for deal context
3. **Phase 4:** Calendar integration for meeting-aware scheduling
4. **Phase 5:** AI summarization of task context

## Tech Stack

- **Backend:** Python 3, FastAPI, SQLAlchemy, Alembic
- **Database:** SQLite (dev), PostgreSQL (prod)
- **CLI:** Click, Rich, httpx
- **Notifications:** Slack SDK
- **CI/CD:** GitHub Actions, Docker, Railway
