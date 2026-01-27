# Ivan Task Manager

Unified task management system that aggregates tasks from multiple sources.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Ivan Task Manager                        │
├─────────────┬─────────────┬─────────────┬─────────────────┤
│  ClickUp    │   GitHub    │    Slack    │      Email      │
│  (Tamás)    │  (Attila)   │  (Pinging)  │   (Search)      │
└─────────────┴─────────────┴─────────────┴─────────────────┘
```

## Systems

| System | Purpose | Users |
|--------|---------|-------|
| **ClickUp** | Business/marketing tasks | Ivan + Tamás |
| **GitHub** | Technical tasks + briefs | Ivan + Attila |
| **Slack** | Notifications + pinging | All |
| **Email** | Context search + threads | All |

## Current Status

- [x] ClickUp integration (via `~/.claude/plugins/clickup/`)
- [x] GitHub integration (via `gh` CLI)
- [ ] Slack integration (research in progress)
- [ ] Email integration (research in progress)

## Directory Structure

```
ivan-task-manager/
├── README.md
├── docs/
│   ├── architecture.md      # System design
│   ├── workflows.md         # How tasks flow between systems
│   └── integrations/        # Per-integration docs
├── scripts/
│   └── task-manager.rb      # Main CLI tool
└── integrations/
    ├── clickup/             # ClickUp MCP/scripts
    ├── github/              # GitHub helpers
    ├── slack/               # Slack integration
    └── email/               # Email integration
```

## Key Principles

1. **No duplicate administration** — Each task lives in ONE system only
2. **Cross-references allowed** — Link between systems, don't copy
3. **Clear ownership:**
   - ClickUp = Ivan + Tamás (business, marketing, sales)
   - GitHub = Ivan + Attila (technical, architecture, bugs)

## Integration Research

### Slack

**Options:**
1. **Slack App + Bot Token** (recommended)
   - Create app at https://api.slack.com/apps
   - Scopes needed: `chat:write`, `users:read`, `channels:read`
   - Can send DMs, post to channels, search messages

2. **Slack MCP Server**
   - Community MCP servers exist for Slack
   - Would integrate directly with Claude Code

### Email (Gmail)

**Options:**
1. **Extend existing Google OAuth**
   - Already have OAuth setup for Docs/Drive
   - Add Gmail scope: `https://www.googleapis.com/auth/gmail.readonly`
   - Use existing `~/.claude/plugins/google-workspace/`

2. **Gmail MCP Server**
   - Build on existing google-workspace plugin
   - Add `gmail_manager.rb` script

## Next Steps

1. [ ] Set up Slack app and get bot token
2. [ ] Extend Google OAuth for Gmail access
3. [ ] Build unified CLI that queries all systems
4. [ ] Create notification workflows (task assigned → Slack ping)

---
*Last updated: 2026-01-27*
