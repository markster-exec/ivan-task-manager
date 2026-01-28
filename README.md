# Ivan Task Manager

Unified task management system that aggregates tasks from ClickUp and GitHub, provides intelligent prioritization, and delivers actionable notifications via Slack.

## Features

- **Multi-source sync**: ClickUp and GitHub tasks synced hourly with retry logic
- **Smart prioritization**: Revenue impact, blocking status, and urgency scoring
- **Single focus**: Always know the ONE task to work on next
- **Slack bot**: Interactive bot with natural language support (Socket Mode)
- **Slack notifications**: Morning briefings, urgent alerts, hourly digests
- **CLI & API**: Both command-line and REST API interfaces
- **Error resilience**: Exponential backoff, graceful degradation

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/markster-exec/ivan-task-manager.git
cd ivan-task-manager

# Install CLI
pip install -e cli/

# Or use Docker
docker-compose up
```

### CLI Usage

```bash
ivan next      # Show highest priority task
ivan done      # Mark current task complete, show next
ivan skip      # Skip current task, show next
ivan tasks     # List all tasks sorted by priority
ivan morning   # Morning briefing
ivan sync      # Force sync from all sources
ivan blocking  # Show who's waiting on you
```

### Slack Bot Commands

DM the bot or mention it in a channel:

| Command | Aliases | Description |
|---------|---------|-------------|
| `next` | "what should I work on?" | Get highest priority task |
| `done` | "finished", "completed" | Mark current task complete |
| `skip` | "later", "not now" | Skip to next task |
| `tasks` | "show my tasks", "list" | List all tasks |
| `morning` | "briefing", "brief me" | Morning summary |
| `sync` | "refresh", "update" | Force sync from sources |
| `help` | "commands", "?" | Show available commands |

Natural language is also supported via Azure OpenAI intent classification.

### Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:

| Variable | Description |
|----------|-------------|
| `CLICKUP_API_TOKEN` | ClickUp API token |
| `CLICKUP_LIST_ID` | ClickUp list to sync |
| `GITHUB_TOKEN` | GitHub personal access token |
| `GITHUB_REPO` | GitHub repo (owner/name) |
| `SLACK_BOT_TOKEN` | Slack bot token (xoxb-) |
| `SLACK_APP_TOKEN` | Slack app token for Socket Mode (xapp-) |
| `SLACK_IVAN_USER_ID` | Slack user ID for DMs |

Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_OPENAI_API_KEY` | - | For natural language classification |
| `MORNING_BRIEFING_TIME` | 07:00 | Daily briefing time |
| `SYNC_INTERVAL_MINUTES` | 60 | Sync frequency |
| `QUIET_HOURS_START` | 22:00 | Notification quiet start |
| `QUIET_HOURS_END` | 07:00 | Notification quiet end |

## Scoring Algorithm

Tasks are scored using this formula:

```
Score = (Revenue × 1000) + (Blocking × 500 × count) + (Urgency × 100) + Recency
```

| Factor | Points | Description |
|--------|--------|-------------|
| Revenue | 1000 | Task has revenue/deal/client tag |
| Blocking | 500 each | Per person waiting on this task |
| Urgency | 500 | Overdue |
| Urgency | 400 | Due today |
| Urgency | 300 | Due this week |
| Urgency | 100 | Future/no deadline |
| Recency | 1 | Activity in last 24h |

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
         │ (hourly+retry)  │                   │
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
       ┌──────────┼──────────┐                 │
       ▼          ▼          ▼                 ▼
┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐
│ CLI (ivan)│ │ FastAPI   │ │ Notifier  │ │ Slack Bot │
└───────────┘ └───────────┘ └───────────┘ └───────────┘
```

## Development

```bash
# Run tests (29 passing)
cd backend
pytest tests/ -v

# Run linting
ruff check backend/
black backend/

# Run locally
uvicorn app.main:app --reload
```

## API Reference

See [docs/api.md](docs/api.md) for full API documentation.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tasks` | GET | All tasks sorted by priority |
| `/next` | GET | Highest priority task |
| `/done` | POST | Mark current task complete |
| `/skip` | POST | Skip current task |
| `/sync` | POST | Force sync from sources |
| `/morning` | GET | Morning briefing data |

## Deployment

Deployed on Railway with Docker.

**Production URL:** https://backend-production-7a52.up.railway.app

```bash
# Deploy to Railway
railway up

# Or use Docker directly
docker build -t ivan-task-manager .
docker run -p 8000:8000 --env-file .env ivan-task-manager
```

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | Complete | Core (FastAPI, syncers, scoring, CLI) |
| Phase 2 | Complete | Slack bot + notifications |
| Phase 3 | Complete | Error handling, retry logic, CLI polish |
| Phase 4+ | Planned | Entity awareness, project context |

See [docs/plans/2026-01-27-product-vision.md](docs/plans/2026-01-27-product-vision.md) for full roadmap.

## Key Principles

1. **No duplicate administration** - Each task lives in ONE system only
2. **Cross-references allowed** - Link between systems, don't copy
3. **Clear ownership** - ClickUp for business, GitHub for technical
4. **Revenue first** - Always prioritize revenue-generating tasks
5. **Unblock others** - Clear blockers quickly (people are waiting)

## License

Internal use only.

---
*Last updated: 2026-01-27*
