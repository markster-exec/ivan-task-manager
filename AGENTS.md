# AGENTS

These instructions define the baseline expectations for Codex agents working in this repo.

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
- `backend/app/main.py` — FastAPI application
- `backend/app/syncer.py` — ClickUp/GitHub task sync
- `backend/app/scorer.py` — Task prioritization logic
- `backend/app/notifier.py` — Slack notifications
- `cli/ivan.py` — CLI client

### Testing
- Run tests: `pytest backend/tests/`
- Lint: `ruff check backend/`
- Format: `black backend/`

### Environment Variables
See `.env.example` for required configuration.
