# AGENTS

Repository-specific instructions for ivan-task-manager. Global standards in `~/.codex/AGENTS.md`.

## Mission

Unified task management system that aggregates tasks from ClickUp and GitHub, provides intelligent prioritization, and delivers actionable notifications via Slack.

## Quick Reference

| Item | Value |
|------|-------|
| Live | https://backend-production-7a52.up.railway.app |
| Repo | https://github.com/markster-exec/ivan-task-manager |
| Stack | Python 3, FastAPI, SQLAlchemy, PostgreSQL (prod) |
| State | **Read `STATE.md` for current position** |
| Dedicated Account | ivan2@markster.ai |

**IMPORTANT:** This project has a dedicated Claude account (ivan2).
- Use `STATE.md` in THIS repo for state tracking
- Do NOT read/write the global `~/Developer/SESSION_STATE.md`
- That file is for the main coordinator account only

## Session Protocol (MANDATORY)

Every session MUST follow this sequence:

### 1. Read STATE.md
Understand current position before doing anything.

### 2. Brainstorm if new work
Use `superpowers:brainstorming` skill before implementing anything new.

**Requires brainstorm:**
- New feature or phase
- Design decision needed
- Multiple valid approaches exist

**Skips brainstorm:**
- Bug fix with obvious cause
- Continuing work already designed
- Documentation-only changes

### 3. One logical step
Complete one discrete unit of work. No sprawling changes.

### 4. Run tests
```bash
pytest backend/tests/ -v
```
Tests MUST pass before committing. Never push broken code.

### 5. Update docs
- **STATE.md** — Always update (what you did, what's next)
- **CHANGELOG.md** — If behavior changed
- **README.md** — If user-facing changes (new features, setup, API)

### 6. Commit if tests pass
Ivan is not a dev. If CI passes and no manual/UI testing needed, commit and push.

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `backend/app/` | FastAPI application (main.py, bot.py, syncer.py, scorer.py, notifier.py) |
| `backend/tests/` | pytest test suite |
| `cli/ivan/` | CLI client (`ivan next`, `done`, `skip`, etc.) |
| `docs/` | Documentation with YAML front matter |
| `docs/plans/` | Product vision, roadmaps, design documents |
| `docs/templates/` | Templates for creating new phases |
| `docs/processes/` | Standard processes (how to create phases, etc.) |

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

## Key Files

| File | Purpose |
|------|---------|
| `STATE.md` | Current working state (read first every session) |
| `backend/app/main.py` | FastAPI application + scheduled jobs |
| `backend/app/bot.py` | Slack bot listener (Socket Mode) |
| `backend/app/slack_blocks.py` | Slack Block Kit formatting utilities |
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

## Standards

1. Follow [Markster Development Standard](https://github.com/markster-exec/project-tracker/blob/main/docs/standards/markster-development-standard.md)
2. Commit format: `<type>(<scope>): <summary>`
3. PRs required for main branch
4. Tests required for behavior changes
5. Update `CHANGELOG.md` for behavior changes
6. All docs under `docs/` MUST have YAML front matter

## Creating a New Phase

1. Copy `docs/templates/phase-roadmap-template.md`
2. Create GitHub issues for each sprint
3. Update `STATE.md` with new phase info
