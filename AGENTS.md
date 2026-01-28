# AGENTS

Repository-specific instructions for ivan-task-manager.

---

## Quick Reference

| Item | Value |
|------|-------|
| Layer | **3 - Prioritization** (see `~/.codex/SYSTEM.md`) |
| Live | https://backend-production-7a52.up.railway.app |
| Repo | https://github.com/markster-exec/ivan-task-manager |
| Repo Path | `/Users/ivanivanka/Developer/Work/ivan-task-manager` |
| Stack | Python 3, FastAPI, SQLAlchemy, PostgreSQL (prod) |
| State | **Read `STATE.md` for current position** |
| Dedicated Account | ivan2@markster.ai |

---

## Dedicated Account Rules

This project has a dedicated Claude account (ivan2).

| Rule | Requirement |
|------|-------------|
| State file | Use `STATE.md` in THIS repo only |
| Global state | Do NOT read/write `~/Developer/SESSION_STATE.md` |
| Entity schema | Use `~/.codex/schemas/entity.yaml` |
| Standards | Follow `~/.codex/AGENTS.md` for commits, PRs |

---

## Session Protocol (MANDATORY)

Every session MUST follow this sequence:

### 0. Read System Contract (if architecture work)
**BEFORE any design decisions**, read `~/.codex/SYSTEM.md` to understand:
- The 4-layer architecture
- Core concepts (entity, workstream, intention)
- Decision rules and scoring formula

**Required for:** New features, new phases, architecture decisions, entity work.
**Skip for:** Bug fixes, documentation, continuing existing design.

### 1. Read State + Task Queue
```
STATE.md                  # Current position
docs/tasks/QUEUE.md       # Pending tasks from main account
```

**IMPORTANT:** Main account (ivan) adds tasks to `docs/tasks/QUEUE.md`. Check this file every session for new work. If PENDING tasks exist, work on them in priority order.

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

---

## Git Commands (IMPORTANT)

**Always use absolute paths or `git -C` flag.** Working directory can be unreliable.

```bash
# CORRECT - use git -C with absolute path
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager status
git -C /Users/ivanivanka/Developer/Work/ivan-task-manager log --oneline -10

# WRONG - relies on working directory
git status
git log --oneline -10
```

If a git command fails with "not a git repository", immediately switch to `git -C` with the absolute repo path.

---

## Mission

Layer 3 of the Markster system: **Prioritization**.

- Aggregates tasks from ClickUp and GitHub
- Scores and ranks by urgency, revenue, blocking, entity priority
- Delivers actionable notifications via Slack
- Provides CLI for task management

---

## Entity Integration

Entities live in `entities/` directory. Use canonical schema from `~/.codex/schemas/entity.yaml`.

### Creating an Entity
```bash
cp entities/example.yaml.template entities/firstname-lastname.yaml
# Edit with required fields from canonical schema
```

### Required Fields (from canonical schema)
- `id`: lowercase, hyphenated slug
- `type`: person | company
- `name`: display name
- `relationship_type`: client|prospect|partner|investor|team|vendor|network
- `intention`: "Current → Next → Goal"

### Task-Entity Mapping
1. **GitHub**: `[CLIENT:entity-id]` in title
2. **ClickUp**: `client:entity-id` tag
3. **Overrides**: `entities/mappings.yaml`

---

## Project Structure

| Directory | Purpose |
|-----------|---------|
| `backend/app/` | FastAPI application |
| `backend/tests/` | pytest test suite |
| `cli/ivan/` | CLI client |
| `entities/` | Entity YAML files |
| `docs/plans/` | Design documents |

## Key Files

| File | Purpose |
|------|---------|
| `STATE.md` | Current working state (read first) |
| `backend/app/main.py` | FastAPI + scheduled jobs |
| `backend/app/bot.py` | Slack bot (Socket Mode) |
| `backend/app/scorer.py` | Task prioritization |
| `backend/app/entity_loader.py` | Entity YAML loading |
| `backend/app/entity_mapper.py` | Task-entity mapping |

---

## Commands

```bash
# Development
docker-compose up

# Test (use absolute path)
pytest /Users/ivanivanka/Developer/Work/ivan-task-manager/backend/tests/ -v

# Lint
ruff check /Users/ivanivanka/Developer/Work/ivan-task-manager/backend/

# Format
black /Users/ivanivanka/Developer/Work/ivan-task-manager/backend/

# Deploy
railway up
```

---

## Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tasks` | GET | All tasks sorted by priority |
| `/next` | GET | Highest priority task |
| `/done` | POST | Mark current task complete |
| `/skip` | POST | Skip current task |
| `/sync` | POST | Force sync from sources |
| `/entities` | GET | List all entities |
| `/entities/{id}` | GET | Entity detail |

---

## Environment Variables

**Required:**
- `CLICKUP_API_TOKEN`, `CLICKUP_LIST_ID`
- `GITHUB_TOKEN`, `GITHUB_REPO`
- `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_IVAN_USER_ID`

**Optional:**
- `DATABASE_URL` (default: sqlite)
- `SYNC_INTERVAL_MINUTES` (default: 60)
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`

---

## Standards

1. Follow `~/.codex/AGENTS.md` for commits, PRs, labels
2. Follow `~/.codex/SYSTEM.md` for architecture decisions
3. Use `~/.codex/schemas/entity.yaml` for entity definitions
4. Tests required for behavior changes
5. All docs under `docs/` MUST have YAML front matter

---

## Creating a New Phase

1. **Read `~/.codex/SYSTEM.md`** to understand where this fits in the 4-layer architecture
2. Use `superpowers:brainstorming` to design
3. Create design doc in `docs/plans/`
4. Create GitHub issue for the phase
5. Update `STATE.md` with new phase info
