# Task Management Architecture

## System Boundaries

### ClickUp (Ivan + Tamás)
- **List:** Mesterlista2026 (`901215490741`)
- **Workspace:** Markster (`9012270250`)
- **Task types:** Business, marketing, sales, content, client delivery
- **Framework:** `[TYPE] Verb + Object` with DONE WHEN / INPUTS / NOTES

### GitHub (Ivan + Attila)
- **Repo:** `markster-exec/project-tracker`
- **Task types:** Technical, architecture, bugs, deployments, briefs
- **Format:** `[AREA] TYPE - Description` with Problem / Context / What's Needed

### Slack
- **Purpose:** Real-time notifications, pinging people, quick questions
- **NOT for:** Task tracking (use ClickUp/GitHub)
- **Channels TBD**

### Email
- **Purpose:** Search historical context, external communication threads
- **NOT for:** Task tracking

## Cross-Reference Rules

| Scenario | Action |
|----------|--------|
| Task needs both technical + business work | Create in BOTH systems, link to each other |
| Task assigned to Attila | GitHub only |
| Task assigned to Tamás | ClickUp only |
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
        │ (Attila) │ │ (Tamás)  │ │ (search) │
        └────┬─────┘ └────┬─────┘ └──────────┘
             │            │
             └─────┬──────┘
                   ▼
             ┌──────────┐
             │  Slack   │
             │ (notify) │
             └──────────┘
```

## IDs Reference

### ClickUp
| Entity | ID |
|--------|-----|
| Markster workspace | 9012270250 |
| VEZÉR space | 90123409203 |
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
TBD - need to set up app

### Email
- Ivan: theivanivanka@gmail.com
- OAuth: `~/.claude/.google/`
