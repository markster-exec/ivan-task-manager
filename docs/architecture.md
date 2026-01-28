---
id: ivan-task-manager-architecture
title: Ivan Task Manager - Architecture
type: reference
status: active
owner: ivan
created: 2026-01-27
updated: 2026-01-27
tags: [architecture, system-design, integrations]
---

# Task Management Architecture

## System Boundaries

### ClickUp (Ivan + Tamas)
- **List:** Mesterlista2026 (`901215490741`)
- **Workspace:** Markster (`9012270250`)
- **Task types:** Business, marketing, sales, content, client delivery
- **Framework:** `[TYPE] Verb + Object` with DONE WHEN / INPUTS / NOTES

### GitHub (Ivan + Attila)
- **Repo:** `markster-exec/project-tracker`
- **Task types:** Technical, architecture, bugs, deployments, briefs
- **Format:** `[AREA] TYPE - Description` with Problem / Context / What's Needed

### Slack
- **Purpose:** Real-time notifications, interactive bot, pinging people
- **Bot:** Socket Mode for real-time messaging
- **NOT for:** Task tracking (use ClickUp/GitHub)

### Email
- **Purpose:** Search historical context, external communication threads
- **NOT for:** Task tracking

## Cross-Reference Rules

| Scenario | Action |
|----------|--------|
| Task needs both technical + business work | Create in BOTH systems, link to each other |
| Task assigned to Attila | GitHub only |
| Task assigned to Tamas | ClickUp only |
| Task assigned to Ivan | Depends on nature (technical → GitHub, business → ClickUp) |
| Need to notify someone | Slack ping with link to task |
| Need historical context | Search email |

## Data Flow

```
                    ┌──────────────┐
                    │   INTAKE     │
                    │ (meetings,   │
                    │  requests)   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Technical│ │ Business │ │ External │
        │   Task   │ │   Task   │ │  Thread  │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  GitHub  │ │ ClickUp  │ │  Email   │
        │ (Attila) │ │ (Tamas)  │ │ (search) │
        └────┬─────┘ └────┬─────┘ └──────────┘
             │            │
             └─────┬──────┘
                   ▼
        ┌─────────────────────┐
        │ Ivan Task Manager   │
        │ (sync, score, serve)│
        └─────────┬───────────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ CLI (ivan)│ │ Slack Bot │ │ FastAPI   │
└───────────┘ └───────────┘ └───────────┘
```

## Component Details

### Syncer (`syncer.py`)
- Syncs from ClickUp and GitHub hourly
- Retry logic with exponential backoff (1s → 2s → 4s)
- Error categorization (auth, permission, rate_limit, etc.)
- Graceful degradation (one source failure doesn't block others)

### Scorer (`scorer.py`)
- Revenue: +1000 points
- Blocking: +500 points per person waiting
- Urgency: +500 (overdue) / +400 (today) / +300 (this week) / +100 (future)
- Recency: +1 if activity in last 24h

### Bot (`bot.py`)
- Socket Mode for real-time Slack messaging
- Command handlers: next, done, skip, tasks, morning, sync, help
- Natural language via regex patterns
- Azure OpenAI intent classification fallback

### Notifier (`notifier.py`)
- Instant alerts for score >= 1000
- Morning briefing at configured time
- Hourly digest for non-urgent updates
- Quiet hours support
- Duplicate prevention via message hashing

## IDs Reference

### ClickUp
| Entity | ID |
|--------|-----|
| Markster workspace | 9012270250 |
| VEZER space | 90123409203 |
| Mesterlista2026 list | 901215490741 |
| Ivan Ivanka | 54476784 |
| Tamas Kiss | 2695145 |
| Attila Sukosd | 81842673 |

### GitHub
| Entity | Value |
|--------|-------|
| Org | markster-exec |
| Repo | project-tracker |
| Ivan | ivanivanka |
| Attila | atiti |

### Slack
| Entity | ID |
|--------|-----|
| Ivan | U084S552VRD |
| Tamas | U0853TD9VFF |
| Attila | U0856NMSALA |

### Email
- Ivan: theivanivanka@gmail.com
- OAuth: `~/.claude/.google/`
