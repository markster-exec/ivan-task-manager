---
id: ivan-task-manager-slack-integration
title: Ivan Task Manager - Slack Integration
type: reference
status: active
owner: ivan
created: 2026-01-27
updated: 2026-01-28
tags: [slack, integration, bot, notifications, block-kit]
---

# Slack Integration

## Overview

Slack integration enables:
- **Interactive bot** for natural language task queries
- **Notifications** for urgent tasks, morning briefings, hourly digests
- Pinging team members about tasks
- Posting task updates to channels

## Current Implementation (bot.py)

The Slack bot is fully implemented using Socket Mode for real-time messaging.

**Commands:**
| Command | Aliases | Description |
|---------|---------|-------------|
| `next` | "what should I work on?", "what's next?" | Show highest priority task |
| `done` | "finished", "completed", "✓" | Mark current task complete |
| `skip` | "later", "skip this" | Skip current task |
| `tasks` | "show my tasks", "list tasks" | List all tasks sorted by priority |
| `morning` | "briefing", "daily brief" | Morning briefing with top 3 tasks |
| `sync` | "refresh", "update" | Force sync from sources |
| `help` | | Show available commands |

**Features:**
- Socket Mode (no public URL required)
- Regex pattern matching for command recognition
- Azure OpenAI intent classification fallback for natural language
- Hourly digest job (runs at :30 each hour)
- Instant alerts for high-priority tasks (score >= 1000)
- Quiet hours support (22:00 - 07:00)
- Duplicate notification prevention via message hashing
- **Block Kit formatting** for rich, structured messages
- **Thread handling** (`thread_ts`) for conversational context
- **Clickable task links** using Slack mrkdwn `<URL|text>` format

**Message Formatting:**

All bot responses use Slack Block Kit for improved readability:
- Headers and dividers for visual hierarchy
- Context blocks for metadata (score, urgency)
- Section blocks for task details
- Inline clickable links to task sources

**Thread Support:**

The bot maintains conversation context:
- Replies in the same thread when responding to thread messages
- Uses `thread_ts` for DMs and @mentions
- Enables natural back-and-forth conversation about tasks

**Environment Variables:**
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_IVAN_USER_ID=U084S552VRD
```

## Historical Options

### Option 1: Slack MCP Server (Recommended)

**Best for:** Direct integration with Claude Code

**Source:** [korotovsky/slack-mcp-server](https://github.com/korotovsky/slack-mcp-server)

**Features:**
- No special permissions required
- Supports DMs, Group DMs, channels
- Smart history fetch (by date or count)
- Works via OAuth or stealth mode
- Stdio and SSE transports

**Setup:**
```bash
# Clone and install
git clone https://github.com/korotovsky/slack-mcp-server.git
cd slack-mcp-server
npm install

# Configure in ~/.mcp.json or ~/.codex/config.toml
```

### Option 2: Custom Slack App + Bot Token

**Best for:** Fine-grained control, custom workflows

**Setup Steps:**
1. Go to https://api.slack.com/apps
2. Create New App → From Scratch
3. Name: "Ivan Task Manager"
4. Select your workspace
5. Go to OAuth & Permissions
6. Add scopes:
   - `chat:write` (send messages)
   - `channels:read` (list channels)
   - `users:read` (get user IDs)
   - `im:write` (send DMs)
7. Install to Workspace
8. Copy Bot Token (starts with `xoxb-`)
9. Store in `~/.claude/.slack/bot_token`

**Usage:**
```bash
# Send message to channel
curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel":"C123456","text":"Hello!"}'

# Send DM (need user ID, not username)
curl -X POST https://slack.com/api/chat.postMessage \
  -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"channel":"U123456","text":"Hey, check this task"}'
```

### Option 3: Composio (Third-party)

**Best for:** Quick setup, managed auth

**Source:** [Composio Slack MCP](https://composio.dev/blog/how-to-use-slack-mcp-server-with-claude-flawlessly)

**Trade-offs:**
- Easier setup
- Third-party dependency
- May have usage limits

## Recommendation

**For self-hosted control:** Option 2 (Custom Slack App)
- Full control over permissions
- No third-party dependencies
- Can build custom workflows

**For quick MCP integration:** Option 1 (slack-mcp-server)
- Works directly with Claude Code
- Active open-source project

## Setup Complete ✅

1. [x] Create Slack App at api.slack.com/apps
2. [x] Add required scopes (chat:write, channels:read, users:read, im:write, app_mentions:read)
3. [x] Enable Socket Mode
4. [x] Install to workspace
5. [x] Store bot token securely
6. [x] Implement bot.py with command handlers
7. [x] Add Azure OpenAI intent classification
8. [x] Implement notifier.py for scheduled notifications
9. [x] Test all commands

## Recent Updates (Phase 4A)

- [x] **Block Kit formatting** - Rich message layout with headers, dividers, sections
- [x] **Thread handling** - Replies maintain conversation context
- [x] **Clickable URLs** - All task references are now clickable links
- [x] **Consistent format** - All handlers return structured responses

## Future Enhancements (Phase 4B+)

- [ ] Bidirectional sync (update tasks via Slack commands)
- [ ] Interactive buttons for task actions (Block Kit actions)
- [ ] Channel-based project updates
- [ ] File/document input handling
- [ ] Screenshot processing for context extraction

## Resources

- [Slack API Token Tutorial](https://api.slack.com/tutorials/tracks/getting-a-token)
- [Slack Web API](https://api.slack.com/web)
- [slack-mcp-server GitHub](https://github.com/korotovsky/slack-mcp-server)
