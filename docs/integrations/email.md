# Email Integration (Gmail)

## Overview

Email integration enables:
- Searching historical email threads for context
- Finding communication history with specific people
- Retrieving attachments or links mentioned in emails

## Approach: Extend Existing Google OAuth

We already have Google OAuth set up for Docs/Drive at:
- Credentials: `~/.claude/.google/client_secret.json`
- Token: `~/.claude/.google/token.json`
- Plugin: `~/.claude/plugins/google-workspace/`

**Plan:** Add Gmail scope and create `gmail_manager.rb`

## Required Scope

Add to existing OAuth:
```
https://www.googleapis.com/auth/gmail.readonly
```

This allows:
- Search emails
- Read email content
- List threads and messages
- NO sending/modifying (read-only for safety)

## Setup Steps

### 1. Update OAuth Scopes

Edit the Google Cloud Console OAuth consent screen:
1. Go to https://console.cloud.google.com/
2. Select your project
3. APIs & Services → OAuth consent screen
4. Add scope: `gmail.readonly`

### 2. Re-authorize

```bash
# Delete existing token to force re-auth
rm ~/.claude/.google/token.json

# Run any google-workspace command to trigger OAuth
~/.claude/plugins/google-workspace/scripts/docs_manager.rb read <any-doc-id>

# This will open browser for consent with new scope
```

### 3. Create gmail_manager.rb

Add to `~/.claude/plugins/google-workspace/scripts/`:

```ruby
#!/opt/homebrew/opt/ruby/bin/ruby
# Gmail Manager for Claude Code

require 'google/apis/gmail_v1'
require 'googleauth'
require 'googleauth/stores/file_token_store'

# Commands:
# - search --query "from:someone subject:topic"
# - read --message-id <id>
# - list-threads --max 10
```

## Gmail API Endpoints

| Action | Method |
|--------|--------|
| Search | `users.messages.list` with `q` parameter |
| Read message | `users.messages.get` |
| List threads | `users.threads.list` |
| Get thread | `users.threads.get` |

## Example Queries

```bash
# Find emails from Attila about Kyle
gmail_manager.rb search --query "from:attila subject:kyle"

# Find emails with attachments from last week
gmail_manager.rb search --query "has:attachment newer_than:7d"

# Read specific thread
gmail_manager.rb get-thread --thread-id <id>
```

## Security Notes

- **Read-only scope** — cannot send or modify emails
- Token stored locally, not in repo
- Can revoke access at https://myaccount.google.com/permissions

## Next Steps

1. [ ] Add gmail.readonly scope in Google Cloud Console
2. [ ] Re-authorize OAuth flow
3. [ ] Create `gmail_manager.rb` script
4. [ ] Test search functionality
5. [ ] Document common search patterns

## Resources

- [Gmail API Reference](https://developers.google.com/gmail/api/reference/rest)
- [Gmail Search Operators](https://support.google.com/mail/answer/7190)
- [Ruby Gmail API Quickstart](https://developers.google.com/gmail/api/quickstart/ruby)
