# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-01-27

### Added
- Initial release
- Task syncing from ClickUp and GitHub
- Priority scoring algorithm (Revenue → Blocking → Urgency → Recency)
- FastAPI backend with REST endpoints
- CLI client (`ivan`) with rich output
- Slack notifications (instant alerts, morning briefings, hourly digests)
- SQLite database for task caching
- Docker support with multi-stage builds
- GitHub Actions CI pipeline
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
