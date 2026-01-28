# AGENTS

These instructions define the baseline expectations for Codex agents working in this repo.

## Required Reading (BEFORE ANY WORK)

**STOP. Before doing any development work, you MUST read:**

1. **`docs/plans/2026-01-27-product-vision.md`** — The product vision and blueprint

This document explains:
- What we're building (AI Chief of Staff for a CEO with multiple companies)
- The 4-layer architecture (Capture → Context → Prioritization → Execution)
- Entity-centric design (entities have intentions, workstreams, deadlines)
- Implementation phases and what's already complete
- How this repo fits into the larger agent-system vision

**Any development work must align with this vision.** Do not add features or make architectural decisions without understanding the full picture.

If the vision document doesn't exist or has been superseded, check for newer files in `docs/plans/` sorted by date.

---

## Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | **Complete** | Core (FastAPI, syncers, scoring, CLI) |
| Phase 2 | **Complete** | Slack bot + notifications |
| Phase 3 | **Complete** | Error handling, retry logic, CLI polish |
| Phase 4+ | Planned | Entity awareness, project context |

**Next priority:** Entity awareness (task-entity mapping, project deadlines)

---

## Standards

1. Produce production-ready code.
2. Write tests for every change (skip only for docs/config-only updates and note why).
3. Run the relevant tests for every change (if no tests exist, state that explicitly).
4. Document non-obvious logic inline.
5. For larger features (new commands, workflows, or multi-file behavior changes), add documentation in `docs/` as markdown.
6. Maintain `CHANGELOG.md` with each improvement that changes behavior or user-facing output.
7. Use the standard commit message format described below.
8. For user interfaces (including CLI UX), add user-facing documentation describing each feature.
9. The dev-docs MCP tool must be used to look up relevant API/documentation when applicable; use list_metadata to review available datasets, search to locate material, and get_chunk to retrieve the exact passages.

## Commit Message Format

Use `<type>(<scope>): <summary>` where:
- `type` is one of: feat, fix, docs, test, chore, refactor, perf, ci
- `scope` is optional and should be a short noun
- `summary` is a short, imperative description

## Project-Specific Instructions

### Stack
- Backend: Python 3, FastAPI, SQLAlchemy, Alembic
- Database: SQLite (dev), PostgreSQL (production on Railway)
- AI: Azure OpenAI (GPT 5.2) — endpoint at `https://ai-devteam-resource.cognitiveservices.azure.com`
- Deployment: Docker containers on Railway

### Key Files

| File | Purpose |
|------|---------|
| `docs/plans/2026-01-27-product-vision.md` | **Product vision (read first!)** |
| `backend/app/main.py` | FastAPI application + scheduled jobs |
| `backend/app/bot.py` | Slack bot listener (Socket Mode) |
| `backend/app/syncer.py` | ClickUp/GitHub sync with retry logic |
| `backend/app/scorer.py` | Task prioritization logic |
| `backend/app/notifier.py` | Slack notifications |
| `backend/app/models.py` | SQLAlchemy models |
| `cli/ivan/__init__.py` | CLI client |

### Testing

```bash
# Run tests (29 passing)
pytest backend/tests/ -v

# Lint
ruff check backend/

# Format
black backend/
```

### Environment Variables

See `.env.example` for required configuration.

### Deployment

- **Production URL:** https://backend-production-7a52.up.railway.app
- **CI:** GitHub Actions (lint, test, build)
- All changes must pass CI before merge.
