# Slack Integration

## Overview

Slack integration enables:
- Pinging team members about tasks
- Posting task updates to channels
- Searching conversation history for context

## Options

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

## Next Steps

1. [ ] Create Slack App at api.slack.com/apps
2. [ ] Add required scopes
3. [ ] Install to workspace
4. [ ] Store bot token securely
5. [ ] Create `slack_manager.rb` script (similar to clickup_manager.rb)
6. [ ] Test sending messages

## Resources

- [Slack API Token Tutorial](https://api.slack.com/tutorials/tracks/getting-a-token)
- [Slack Web API](https://api.slack.com/web)
- [slack-mcp-server GitHub](https://github.com/korotovsky/slack-mcp-server)
