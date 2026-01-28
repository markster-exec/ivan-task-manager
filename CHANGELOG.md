# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Entity awareness (task-entity mapping)
- Project context inheritance for deadlines
- Bidirectional sync (write back to ClickUp/GitHub)
- HubSpot integration

## [0.3.0] - 2026-01-27

### Added (Phase 3: Polish + Error Handling)
- Error categorization for sync failures (auth, permission, rate_limit, timeout, connection, server)
- Retry logic with exponential backoff (1s → 2s → 4s, max 30s)
- Graceful degradation when sources are unavailable
- CLI progress spinners for all commands
- Improved CLI error messages with troubleshooting tips

### Changed
- Syncer now continues when one source fails (ClickUp failure doesn't block GitHub)
- SyncState now stores detailed error messages
- CLI shows connection help when API unreachable

## [0.2.0] - 2026-01-27

### Added (Phase 2: Slack Bot + Notifications)
- Slack bot listener using Socket Mode
- Command handlers: next, done, skip, tasks, morning, sync, help
- Natural language patterns via regex matching
- Azure OpenAI intent classification fallback for unrecognized messages
- Hourly digest job (runs at :30 each hour)
- DigestState model to track last digest timestamp

### Changed
- Bot module uses lazy initialization (create_app pattern)
- Bot can be imported without slack_bolt installed (for tests)
- main.py conditionally starts bot if SLACK_APP_TOKEN is set

## [0.1.0] - 2026-01-27

### Added (Phase 1: Core)
- Initial release
- Task syncing from ClickUp and GitHub
- Priority scoring algorithm (Revenue → Blocking → Urgency → Recency)
- FastAPI backend with REST endpoints
- CLI client (`ivan`) with rich output
- Slack notifications (instant alerts, morning briefings, hourly digests)
- SQLite database for task caching
- Docker support with multi-stage builds
- GitHub Actions CI pipeline (lint, test, build)
- Quiet hours support for notifications
- Duplicate notification prevention

### API Endpoints
- `GET /health` - Health check
- `GET /tasks` - List all tasks sorted by priority
- `GET /next` - Get highest priority task
- `POST /done` - Mark current task complete
- `POST /skip` - Skip current task
- `POST /sync` - Force sync from sources
- `GET /morning` - Morning briefing data

### CLI Commands
- `ivan next` - Show highest priority task
- `ivan done` - Mark current task complete
- `ivan skip` - Skip current task
- `ivan tasks` - List all tasks
- `ivan morning` - Morning briefing
- `ivan sync` - Force sync
- `ivan blocking` - Show who's waiting on you
