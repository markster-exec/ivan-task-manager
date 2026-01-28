---
id: ivan-task-manager-overview
title: Ivan Task Manager - Overview
type: reference
status: active
owner: ivan
created: 2026-01-27
updated: 2026-01-27
tags: [task-management, prioritization, slack, clickup, github]
---

# Ivan Task Manager

A unified task management system that aggregates tasks from ClickUp and GitHub, provides intelligent prioritization, and delivers actionable notifications via Slack.

## Overview

Ivan Task Manager solves the "multiple task systems" problem by:
1. Syncing tasks from ClickUp and GitHub hourly (with retry logic)
2. Scoring tasks by revenue impact, blocking status, and urgency
3. Surfacing the single most important task to work on
4. Sending morning briefings and urgent task alerts via Slack
5. Providing an interactive Slack bot for natural language queries

## Quick Start

### CLI Usage

```bash
# Show highest priority task
ivan next

# Mark current task complete, show next
ivan done

# Skip current task, show next
ivan skip

# List all tasks sorted by priority
ivan tasks

# Morning briefing
ivan morning

# Force sync from all sources
ivan sync

# Show who's waiting on you
ivan blocking
```

### Slack Bot

DM the bot or mention it:
- `next` / "what should I work on?"
- `done` / "finished"
- `skip` / "later"
- `tasks` / "show my tasks"
- `morning` / "briefing"
- `sync` / "refresh"
- `help`

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/tasks` | GET | All tasks sorted by priority |
| `/next` | GET | Highest priority task |
| `/done` | POST | Mark current task complete |
| `/skip` | POST | Skip current task |
| `/sync` | POST | Force sync from all sources |
| `/morning` | GET | Morning briefing data |

## Scoring Algorithm

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

## Configuration

All configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CLICKUP_API_TOKEN` | ClickUp API token | Required |
| `CLICKUP_LIST_ID` | ClickUp list to sync | Required |
| `GITHUB_TOKEN` | GitHub personal access token | Required |
| `GITHUB_REPO` | GitHub repo (owner/name) | Required |
| `SLACK_BOT_TOKEN` | Slack bot token | Required |
| `SLACK_APP_TOKEN` | Slack app token (Socket Mode) | Required for bot |
| `SLACK_IVAN_USER_ID` | Slack user ID for DMs | Required |
| `DATABASE_URL` | Database connection string | sqlite:///./tasks.db |
| `SYNC_INTERVAL_MINUTES` | Sync frequency | 60 |
| `MORNING_BRIEFING_TIME` | Daily briefing time | 07:00 |
| `QUIET_HOURS_START` | Notification quiet start | 22:00 |
| `QUIET_HOURS_END` | Notification quiet end | 07:00 |

## Deployment

Runs on Railway with Docker.

**Production URL:** https://backend-production-7a52.up.railway.app

```bash
# Local development
docker-compose up

# Production
railway up
```
