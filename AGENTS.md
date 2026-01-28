# AGENTS

Repository-specific instructions for ivan-task-manager. Global standards in `~/.codex/AGENTS.md`.

## Mission

Unified task management system that aggregates tasks from ClickUp and GitHub, provides intelligent prioritization, and delivers actionable notifications via Slack.

**Live:** https://backend-production-7a52.up.railway.app
**Repo:** https://github.com/markster-exec/ivan-task-manager

## Map

| Directory | Purpose |
|-----------|---------|
| `backend/app/` | FastAPI application (main.py, bot.py, syncer.py, scorer.py, notifier.py) |
| `backend/tests/` | pytest test suite (29 tests) |
| `cli/ivan/` | CLI client (`ivan next`, `done`, `skip`, etc.) |
| `docs/` | Documentation with YAML front matter |
| `docs/plans/` | Product vision and design documents |

## Context Recovery

**BEFORE ANY WORK, read these in order:**

1. `docs/plans/2026-01-28-phase-4-roadmap.md` — Current implementation plan with 5 sprints
2. `docs/plans/2026-01-27-product-vision.md` — Overall product vision and architecture
3. Check GitHub issues: `gh issue list --repo markster-exec/project-tracker --label "area:product" --state open`

**Track progress on GitHub:**
- Issues #24-28 in `markster-exec/project-tracker` track Phase 4 sprints
- Update issue comments when starting/completing work
- Reference issues in commits: `feat(bot): add links (project-tracker#24)`

## Workflow

**Before starting:** Read Context Recovery section above.

**Before finishing:** Update `CHANGELOG.md`, run tests, ensure CI passes.

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1-3 | **Complete** | Core, Slack bot, error handling, CLI |
| Phase 4A | Planned | Bot communication fix (links, threading) |
| Phase 4B | Planned | Entity awareness (context for tasks) |
| Phase 4C | Planned | Bidirectional sync (write to sources) |
| Phase 4D | Planned | Rich Slack input (files, docs) |
| Phase 4E | Planned | Image/screenshot processing |

**Next:** Phase 4A — See `docs/plans/2026-01-28-phase-4-roadmap.md` for full spec.

**GitHub Issues:** #24 (4A), #25 (4B), #26 (4C), #27 (4D), #28 (4E) in `markster-exec/project-tracker`

## Commands

```bash
# Development
docker-compose up

# Test
pytest backend/tests/ -v

# Lint
ruff check backend/

# Format
black backend/

# Deploy
railway up
```

## Environment Variables

**Required:**
- `CLICKUP_API_TOKEN` - ClickUp API token
- `CLICKUP_LIST_ID` - ClickUp list to sync (default: 901215490741)
- `GITHUB_TOKEN` - GitHub personal access token
- `GITHUB_REPO` - GitHub repo (owner/name)
- `SLACK_BOT_TOKEN` - Slack bot token (xoxb-...)
- `SLACK_APP_TOKEN` - Slack app token for Socket Mode (xapp-...)
- `SLACK_IVAN_USER_ID` - Slack user ID for DMs

**Optional:**
- `DATABASE_URL` - Database connection string (default: sqlite:///./tasks.db)
- `SYNC_INTERVAL_MINUTES` - Sync frequency (default: 60)
- `MORNING_BRIEFING_TIME` - Daily briefing time (default: 07:00)
- `QUIET_HOURS_START` - Notification quiet start (default: 22:00)
- `QUIET_HOURS_END` - Notification quiet end (default: 07:00)
- `AZURE_OPENAI_ENDPOINT` - Azure OpenAI for intent classification
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/main.py` | FastAPI application + scheduled jobs |
| `backend/app/bot.py` | Slack bot listener (Socket Mode) |
| `backend/app/syncer.py` | ClickUp/GitHub sync with retry logic |
| `backend/app/scorer.py` | Task prioritization (Revenue → Blocking → Urgency → Recency) |
| `backend/app/notifier.py` | Slack notifications (instant, digest, morning) |
| `backend/app/models.py` | SQLAlchemy models (Task, SyncState, DigestState) |

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tasks` | GET | All tasks sorted by priority |
| `/next` | GET | Highest priority task |
| `/done` | POST | Mark current task complete |
| `/skip` | POST | Skip current task |
| `/sync` | POST | Force sync from sources |
| `/morning` | GET | Morning briefing data |

## Standards

1. Produce production-ready code.
2. Write tests for every change (skip only for docs/config-only updates and note why).
3. Run the relevant tests for every change (if no tests exist, state that explicitly).
4. Document non-obvious logic inline.
5. Maintain `CHANGELOG.md` with each improvement that changes behavior.
6. All docs under `docs/` MUST have YAML front matter (id, title, type, status, owner, created, updated, tags).

## Stack

- Backend: Python 3, FastAPI, SQLAlchemy, Alembic
- Database: SQLite (dev), PostgreSQL (production on Railway)
- AI: Azure OpenAI (GPT 5.2) for intent classification
- Deployment: Docker containers on Railway
- CI: GitHub Actions (lint, test, build)
