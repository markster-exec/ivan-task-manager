---
id: chief-of-staff-bot-design
title: Chief of Staff Bot - Complete Redesign
type: plan
status: active
owner: ivan
created: 2026-01-31
updated: 2026-01-31
tags: [slack-bot, ai-assistant, architecture, design]
---

# Chief of Staff Bot - Complete Redesign

## Overview

Transform the Ivan Task Manager Slack bot from a simple notification system into a full AI-powered chief of staff that can manage tasks, conduct research, process any input, and work across multiple surfaces.

### Problem Statement

Current bot sends individual notifications for each overdue task, creating noise instead of signal. Users cannot take action from Slack, tasks get out of sync, and there's no conversational capability.

### Solution

A three-surface architecture (Slack, Claude Code, ivan-os) with shared state, smart escalation notifications, hybrid button/natural language interactions, and full assistant capabilities including research and multi-modal input processing.

---

## Architecture

### Three Surface Model

```
┌─────────────────────────────────────────────────────────────────┐
│                        SURFACES                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│     SLACK       │   CLAUDE CODE   │         IVAN-OS             │
│    (GPT-5.2)    │    (Claude)     │    (Autonomous Agent)       │
├─────────────────┼─────────────────┼─────────────────────────────┤
│ Quick actions   │ Deep work       │ Background tasks            │
│ Alerts/notifs   │ Complex research│ Scheduled operations        │
│ Mobile/async    │ Code changes    │ Autonomous decisions        │
│ Conversations   │ Long context    │ Prompted via web/API        │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         └─────────────────┼───────────────────────┘
                           │
              ┌────────────▼────────────┐
              │      CONTEXT LAYER      │
              ├─────────────────────────┤
              │ Location & Timezone     │
              │  - current, until, home │
              │                         │
              │ Priorities              │
              │  - explicit overrides   │
              │  - learned preferences  │
              │  - time-boxed boosts    │
              │                         │
              │ Calendar                │
              │  - today's events       │
              │  - upcoming travel      │
              │                         │
              │ Conversation History    │
              │  - last N messages      │
              │  - pending handoffs     │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │      SHARED STATE       │
              ├─────────────────────────┤
              │ Tasks (SQLite)          │
              │  - score, status, due   │
              │  - escalation level     │
              │  - snooze until         │
              │                         │
              │ Entities (YAML)         │
              │  - relationship type    │
              │  - active workstreams   │
              │  - channels (docs, etc) │
              │                         │
              │ Action Queue            │
              │  - pending handoffs     │
              │  - scheduled actions    │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     INTEGRATIONS        │
              │  ClickUp, GitHub, Docs  │
              │  Slack, Calendar, Web   │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │      AI ENGINE          │
              ├─────────────────────────┤
              │ Primary: Azure (GPT-5.2)│
              │    ↓ 30s timeout        │
              │ Fallback: ivan-os API   │
              │    ↓                    │
              │ Fallback: Anthropic API │
              │    ↓                    │
              │ Degraded: regex only    │
              └─────────────────────────┘
```

### Surface Capabilities

| Capability | Slack | Claude Code | ivan-os |
|------------|-------|-------------|---------|
| Read tasks | ✓ | ✓ | ✓ |
| Create/update tasks | ✓ | ✓ | ✓ |
| Execute actions (ClickUp, GitHub) | ✓ | ✓ | ✓ |
| Research (web) | ✓ | ✓ | ✓ |
| Queue work for another surface | ✓ | ✓ | ✓ |
| Act autonomously | ✗ | ✗ | ✓ |

### AI Engine Fallback Chain

```python
AI_PROVIDERS = [
    {
        "name": "azure",
        "endpoint": "...",
        "model": "gpt-5.2",
        "timeout": 30  # seconds
    },
    {
        "name": "ivan-os",
        "endpoint": "https://ivan-os.fly.dev/api/chat",
        "timeout": 30
    },
    {
        "name": "anthropic",
        "api_key": "...",
        "model": "claude-sonnet",
        "timeout": 30
    },
]
# If all fail: graceful degradation to regex-based commands
```

### Context Injection

Every AI call includes current context:

```python
context = {
    "location": get_current_location(),      # "Los Angeles (PST)"
    "time": get_local_time(),                # "Sat Jan 31, 4:30 PM"
    "priorities": get_active_overrides(),    # [{boost: investor, until: Feb 7}]
    "top_tasks": get_top_tasks(10),          # scored & sorted
    "entities": get_active_entities(),       # clients, prospects with workstreams
    "calendar_today": get_todays_events(),   # meetings, deadlines
    "history": get_recent_messages(10),      # conversation context
}
```

---

## Smart Escalation Notifications

### Escalation Ladder

| Days Overdue | Notification Behavior |
|--------------|----------------------|
| **0 (due today)** | Included in morning briefing only |
| **1** | Mentioned in morning briefing with flag |
| **2** | Appears in afternoon digest (2pm) |
| **3+** | Individual DM with action buttons |
| **5+** | Escalates: "This is now 5 days overdue. Should I delegate or kill it?" |
| **7+** | Final warning: "Removing from active list unless you respond" |

### Consolidation Rule

If 3+ tasks hit the same escalation level on the same day, send one grouped message instead of individual spam.

### 3+ Day Overdue Message Format

```
🔴 *3 days overdue*
"[CREATE] Hand off Mark case study to Attila"
Was due: 2026-01-28

[Defer ▾] [Delegate ▾] [Done] [Snooze ▾]
```

### Button Behaviors

| Button | Behavior |
|--------|----------|
| **Defer ▾** | Dropdown: Tomorrow, 3 days, 1 week, Pick date... |
| **Delegate ▾** | Dropdown: Attila, Tamas, Other... |
| **Done** | Opens thread: "What happened?" → user replies → marks complete with note |
| **Snooze ▾** | Dropdown: 1 day, 3 days, 1 week (hides locally, doesn't change source) |

### Context-Rich Action Flow

For actions that need context (Done, Comment):

```
Bot: "3 days overdue: [CREATE] Hand off Mark case study to Attila"
     [Defer ▾] [Delegate ▾] [Done] [Snooze]

User taps [Done]

Bot: "What happened?" (in thread)

User: "Handed off, he's reviewing by Monday"

Bot: "✅ Marked complete. Added note: 'Handed off, he's reviewing by Monday'"
```

---

## Morning Briefing & Proactive Check-ins

### Morning Briefing (Daily, 7:00 AM local time)

```
☀️ Good morning, Ivan

📍 You're in Los Angeles (PST)

🔥 TOP 3 FOCUS
1. [CLIENT:Kyle] Present offer at LA meeting (Score: 1200)
   → Due today, revenue, client waiting
   [Prep notes] [Snooze until 1hr before] [Done]

2. [BUILD] Maintain 10 active investor conversations (Score: 890)
   → 3 days overdue, 2 replies pending
   [Show replies to answer] [Defer 1 week] [Delegate]

3. [RESEARCH] Review Attila and Tamas networks for referrals (Score: 780)
   → 1 day overdue
   [Start now] [Defer] [Delegate]

📊 SUMMARY
• 12 tasks total, 6 overdue
• 2 due today
• 3 people waiting on you (Kyle, Mark, Attila)

📅 TODAY
• 2:00 PM - Kyle meeting (Google Calendar)
• No other scheduled events

💡 SUGGESTION
You have 5 tasks overdue 3+ days. Want me to bulk-defer
the non-revenue ones to next week?

[Yes, defer them] [Show me the list] [No]
```

### Proactive Check-in Triggers

| Trigger | Message |
|---------|---------|
| **2:00 PM** | Afternoon digest (if new items since morning) |
| **Task aging** | "3 tasks just hit 3 days overdue" (grouped) |
| **Before meeting** | 30min before: "Kyle meeting in 30. Here's context: [brief summary]" |
| **End of day** | "You completed 4 tasks today. 2 still due. Defer to tomorrow?" |
| **Idle detection** | If no `done` in 3 hours during work hours: "Still working on X? Need to switch?" |

### Quiet Hours

No notifications between 10 PM - 7 AM (configurable), except:
- User messages first
- Something marked truly urgent by user

---

## Conversational Assistant

### Capabilities

| Category | Examples |
|----------|----------|
| **Task management** | "Defer all Kyle tasks to next week", "What's overdue?", "Create task: review proposal by Friday" |
| **Entity queries** | "What's happening with Mark?", "Show me Attila's blocked items", "Kyle status" |
| **Schedule/context** | "What do I have due today?", "Clear my afternoon" (defer non-critical), "Focus mode" (snooze everything for 2 hours) |
| **Cross-system** | "Send Tamas a Slack message about the deploy", "Add comment to Kyle doc: ready for review" |
| **Research** | "Find co-working spaces in LA", "What events in SF next week?" |

### Example: Research Request

```
User: "What coworking spaces are good in LA near Santa Monica?"

Bot: I found 3 highly-rated options near Santa Monica:

1. **Second Home** - Hollywood, creative vibe, $350/mo
   → Good for meetings, has podcast rooms

2. **Cross Campus** - Santa Monica, startup crowd, $400/mo
   → Walking distance to beach, 24/7 access

3. **WeWork Lincoln Blvd** - Venice/SM border, $450/mo
   → Most professional, best for client calls

Want me to check availability or save these somewhere?
```

### Example: Event Research

```
User: "What events should I attend in SF next week?"

Bot: Checking your calendar... you're free Feb 5-7.

Found 4 relevant events:

1. **AI Engineer Summit** - Feb 5-6, Moscone
   → Heavy hitters, good for investor intros

2. **Founders Happy Hour** - Feb 6, SOMA
   → Casual, YC crowd

[Create task to register?] [Add to calendar?]
```

---

## Input Processing

### Supported Input Types

| Input | How It's Processed |
|-------|-------------------|
| **Link (article/page)** | Fetches content, summarizes, extracts key points |
| **Link (YouTube)** | Pulls transcript, summarizes, extracts action items |
| **Link (Google Doc)** | Reads via existing integration, summarizes |
| **Image** | GPT-5.2 vision analyzes, describes, extracts text/data |
| **Video file** | Extracts audio → transcribes (Whisper) + samples key frames → vision analysis → combined summary |
| **PDF/File** | Downloads, extracts text, summarizes |
| **Voice memo** | Transcribes (Whisper), then processes as text |
| **Pasted text** | Processes directly — summarize, extract, act on |

### Video Processing Flow

```
Video uploaded
    ↓
┌───┴───┐
│       │
▼       ▼
Audio   Frames (1/30s or scene changes)
│       │
▼       ▼
Whisper GPT-5.2 vision
│       │
▼       ▼
Transcript   Visual context
│       │
└───┬───┘
    ▼
Combined analysis
"Here's what was discussed + what was shown"
```

### Example: Video Processing

```
User: [uploads 2min video clip from conference]
"What's this about?"

Bot: This is a pitch from a startup called "FlowAI" at TechCrunch.

Spoken content:
- B2B workflow automation, $2M ARR
- Asking for $5M Series A

Visuals:
- Demo showed drag-and-drop builder
- Slide: 40% MoM growth chart

Relevant to you? They're in your space.
[Save to research] [Ignore]
```

### Example: Image Processing

```
User: [uploads screenshot of whiteboard]
"Turn this into tasks"

Bot: I see a diagram with 3 workstreams:
- "Kyle onboarding" → deadline visible: Feb 7
- "Investor deck" → marked urgent
- "Hire ops person" → no deadline

Create these as ClickUp tasks?
[Create all] [Let me edit first]
```

---

## Context Visibility & Control

### Status Command

```
User: "status" (or "what's active" / "show overrides")

Bot: 📍 CURRENT CONTEXT

Location: Los Angeles, CA (PST)
  → Until: Feb 5, then back to Budapest

🎯 Active Priorities:
  1. Boost: investor-related (+50%) — until Feb 7
  2. Dampen: client tasks (-30%) — until Feb 7
  3. Pin: Kyle is #1 — no expiry

⏸️ Snoozed:
  - "[BUILD] Send 200 manual outbound" — until Feb 3
  - "[RESEARCH] Review networks" — until Monday

🔕 Quiet Hours: 10 PM - 7 AM

📅 Today:
  - 2:00 PM: Kyle meeting

[Reset all] [Edit priorities] [Change location]
```

### Context Update Commands

| User Says | What Updates |
|-----------|--------------|
| "I'm in LA until Feb 5" | `location.current`, `location.until` |
| "Focus on investors this week" | `priorities.overrides` (boost investors) |
| "Kyle is #1 right now" | `priorities.overrides` (boost Kyle entity) |
| "Ignore non-revenue stuff today" | `priorities.overrides` (dampen non-revenue) |
| "Back to normal" | Clears all temporary overrides |

### Quick Resets

| User Says | What Happens |
|-----------|--------------|
| "Back to normal" | Clears ALL temporary overrides, keeps location |
| "Clear priorities" | Removes boosts/dampens only |
| "Clear snoozes" | Un-snoozes all tasks |
| "I'm home" | Resets location to home timezone |
| "Reset everything" | Full reset: location, priorities, snoozes |

### Context Configuration Files

```yaml
# ~/.ivan/context.yaml
location:
  current: "Los Angeles, CA"
  until: "2026-02-05"
  timezone: "America/Los_Angeles"
  home: "Budapest, Hungary"
  home_timezone: "Europe/Budapest"

language:
  preferred: "auto"  # or "en" / "hu" to force
  hungarian_model: "ivan-os"  # use ivan-os for HU when available
```

```yaml
# ~/.ivan/priorities.yaml
overrides:
  - type: "boost"
    match: "tags contains 'investor'"
    factor: 1.5
    until: "2026-02-07"
  - type: "dampen"
    match: "relationship_type == 'client'"
    factor: 0.7
    until: "2026-02-07"
  - type: "pin"
    entity: "kyle-stearns"
    rank: 1
    until: null  # no expiry
```

---

## Task Dependencies

### Dependency Detection

The bot identifies dependencies when:
- User mentions sequence: "after X", "once Y is done", "blocked by Z"
- Logical inference: "can't send proposal until pricing is approved"

### Example: Creating Dependent Tasks

```
User: "I need to send Kyle the proposal, but first Attila needs to finish the technical spec"

Bot: I see two tasks with a dependency:

1. [Attila] Finish technical spec for Kyle
   → Creates in: GitHub project-tracker (technical)
   → Assigns: Attila

2. [Ivan] Send Kyle the proposal
   → Creates in: ClickUp (client)
   → Blocked by: #1
   → Auto-unblocks when #1 is done

[Create both] [Edit] [Just remind me later]
```

### Dependency Queries

```
User: "What's blocking Kyle stuff?"

Bot: 2 Kyle tasks are blocked:

1. "Send proposal" — waiting on:
   → "Technical spec" (Attila, GitHub, in progress)

2. "Schedule demo" — waiting on:
   → "Send proposal" (you, blocked)

Attila's spec is the bottleneck. Nudge him?
[Message Attila] [Show full chain]
```

---

## Delegation & Routing

### Routing Rules

| Work Type | Assigned To | System | Example |
|-----------|-------------|--------|---------|
| Technical/Engineering | Attila | GitHub project-tracker | "Deploy webhook fix" |
| Marketing/Content | Tamas | ClickUp Mesterlista | "Write blog post" |
| Client work | Ivan | ClickUp (client tag) | "Send Kyle proposal" |
| Research/Ideas | Ivan | ClickUp or local | "Research SF events" |

### Routing Configuration

```yaml
# ~/.ivan/routing.yaml
delegation:
  attila:
    keywords: ["deploy", "fix", "build", "technical", "webhook", "api", "infra"]
    system: github
    repo: markster-exec/project-tracker
    notify: slack

  tamas:
    keywords: ["write", "post", "content", "marketing", "social", "email"]
    system: clickup
    list: mesterlista
    notify: slack

  default:
    system: clickup
    list: mesterlista
```

### Delegation Flow

```
User: "Delegate the webhook fix to Attila"

Bot: Creating in GitHub project-tracker:
  → Title: "[CORE] TASK - Fix webhook retry logic"
  → Assignee: atiti
  → Labels: area:core, priority:high
  → Links to: ClickUp task (if exists)

Notify Attila on Slack?
[Yes, with context] [Just create ticket] [Edit first]
```

```
User: "Tamas should write a post about the new feature"

Bot: Creating in ClickUp Mesterlista:
  → Title: "[WRITE] Blog post about new feature"
  → Assignee: Tamas (2695145)
  → Tags: EN, markster

[Create] [Add more details first]
```

---

## Bilingual Support (EN/HU)

### Language Detection & Response

```
User: "Mi a helyzet Kyle-lal?"

Bot: Kyle / Ace Industrial státusz:

📍 Aktív: Call Center Tech Layer projekt
📅 Következő: Meeting ma 14:00
⚠️ 2 feladat késésben

Tennivalók:
1. Ajánlat bemutatása (ma esedékes)
2. Demo időpont egyeztetés (blokkolt)

[Részletek] [Feladatok megjelenítése]
```

### Language Handling

| User Input | Bot Response |
|------------|--------------|
| English | English |
| Hungarian | Hungarian |
| Mixed | Follows dominant language |
| "Reply in English" | Switches, remembers preference |

### Hungarian Model Routing

```python
# If Hungarian detected and ivan-os available:
if detected_language == "hu" and ivan_os_available:
    # Route to ivan-os Hungarian model for better quality
    response = await ivan_os.chat(message, model="hungarian")
else:
    # Azure GPT-5.2 handles it (still works, slightly less natural)
    response = await azure.chat(message)
```

---

## Action Logging & Audit Trail

### Log Directory Structure

```
~/.ivan/logs/
├── actions/
│   ├── 2026-01-31.jsonl      # Daily action log
│   └── 2026-02-01.jsonl
├── conversations/
│   ├── slack-2026-01-31.jsonl
│   └── cli-2026-01-31.jsonl
└── errors/
    └── 2026-01-31.jsonl
```

### Action Log Entry Format

```json
{
  "timestamp": "2026-01-31T16:45:23Z",
  "surface": "slack",
  "action": "task.defer",
  "target": "clickup:abc123",
  "params": {"new_due": "2026-02-03"},
  "result": "success",
  "ai_provider": "azure",
  "latency_ms": 1250,
  "user_input": "push this to monday",
  "context_snapshot": {
    "location": "Los Angeles",
    "active_overrides": ["boost:investor"]
  }
}
```

### What Gets Logged

| Event | Logged Data |
|-------|-------------|
| Task action (done, defer, delegate) | Target, params, result, before/after state |
| AI call | Provider, model, latency, token count, fallback used? |
| Notification sent | Type, recipient, content hash, delivery status |
| Context change | What changed, old value, new value, trigger |
| Error | Full stack trace, context, recovery action |

### Debugging Commands

```
User: "What happened with the Kyle task yesterday?"

Bot: Action history for Kyle tasks (Jan 30):

16:45 - Deferred "Send proposal" to Feb 3
  → You said: "push this to monday"
  → Via: Slack

18:20 - Added comment: "Waiting on spec"
  → You said: "comment waiting on attila's spec"
  → Via: Slack
  → Posted to: ClickUp

[Show full log] [Export to file]
```

```
User: "show error log"

Bot: Last 24h errors:

1. 14:32 - Azure timeout (32s), fell back to ivan-os ✓
2. 09:15 - ClickUp API 429 (rate limit), retried after 60s ✓

No unrecovered errors.
```

### Log Retention

- Action logs: 90 days
- Conversation logs: 30 days
- Error logs: 180 days
- Configurable in settings

---

## Handoffs Between Surfaces

### Slack → Claude Code

```
Slack: "Research investor events in SF, need detailed analysis"

Bot: "This needs deeper research. I've queued it for Claude Code.
     Run `ivan inbox` to pick it up, or I'll include summary
     in tomorrow's briefing."
```

### Claude Code → Slack

```
Claude Code: "Send Tamas a summary of what we discussed"

Claude: Posts to Slack via integration, logs to conversation history
```

### ivan-os → Slack

```
(Autonomous) "I noticed Kyle replied. Here's summary + suggested response."

User approves/edits via buttons
```

### Slack → ivan-os

```
"Monitor Kyle's email replies and alert me when he responds"

ivan-os runs in background, notifies Slack when triggered
```

---

## Implementation Notes

### New Files to Create

- `backend/app/ai_engine.py` - AI provider abstraction with fallback
- `backend/app/context.py` - Context layer management
- `backend/app/escalation.py` - Smart escalation logic
- `backend/app/input_processor.py` - Multi-modal input handling
- `backend/app/action_logger.py` - Audit trail logging
- `backend/app/routing.py` - Delegation routing rules
- `backend/app/dependencies.py` - Task dependency tracking

### Files to Modify

- `backend/app/bot.py` - Replace regex routing with AI-powered routing
- `backend/app/notifier.py` - Add escalation logic, grouped messages
- `backend/app/slack_blocks.py` - Add button interactions, thread flows
- `backend/app/models.py` - Add escalation_level, snooze_until, dependencies

### Configuration Files

- `~/.ivan/context.yaml` - Location, timezone, language
- `~/.ivan/priorities.yaml` - Priority overrides
- `~/.ivan/routing.yaml` - Delegation routing rules
- `~/.ivan/config.yaml` - AI providers, quiet hours, log retention

---

## Success Criteria

1. **No notification spam** - Grouped, escalated, actionable
2. **One-tap actions** - Defer, delegate, done from Slack
3. **Natural conversation** - Research, queries, task management
4. **Process anything** - Links, images, video, files work
5. **Context-aware** - Knows location, priorities, calendar
6. **Full audit trail** - Every action logged and queryable
7. **Graceful degradation** - Works even if AI providers fail
8. **Bilingual** - Seamless EN/HU support
