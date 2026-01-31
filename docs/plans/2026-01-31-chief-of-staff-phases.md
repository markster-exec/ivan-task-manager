---
id: chief-of-staff-phases
title: Chief of Staff Bot - Phased Implementation
type: plan
status: active
owner: ivan
created: 2026-01-31
updated: 2026-01-31
tags: [slack-bot, phases, implementation]
---

# Chief of Staff Bot - Phased Implementation

Breaks the full design into incremental phases. Each phase delivers working value.

**Full design:** `docs/plans/2026-01-31-chief-of-staff-bot-design.md`

---

## Phase Overview

| Phase | Name | Value Delivered |
|-------|------|-----------------|
| 1 | Smart Notifications | No more spam — consolidated, escalated alerts |
| 2 | Button Actions | One-tap defer, done, delegate from Slack |
| 3 | AI Conversations | Natural language task management |
| 4 | Context Layer | Location, priorities, calendar awareness |
| 5 | Input Processing | Process links, images, files |
| 6 | Advanced | Dependencies, routing, video, bilingual |

---

## Phase 1: Smart Notifications

**Goal:** Replace notification spam with consolidated, actionable alerts.

### Deliverables

1. **Escalation ladder**
   - Day 0: Morning briefing only
   - Day 1: Flagged in briefing
   - Day 2: Afternoon digest
   - Day 3+: Individual DM with buttons
   - Day 5+: Escalation prompt
   - Day 7+: Final warning

2. **Morning briefing**
   - Top 3 tasks by score
   - Summary stats (total, overdue, due today)
   - Today's calendar events
   - Runs at 7 AM local time

3. **Consolidation rule**
   - 3+ tasks at same escalation level → one grouped message

4. **Basic buttons** (non-functional placeholders)
   - [Defer] [Done] [Snooze] shown but don't work yet

### Files to Create/Modify

- `backend/app/escalation.py` — escalation logic
- `backend/app/briefing.py` — morning briefing generator
- `backend/app/notifier.py` — modify to use escalation
- `backend/app/models.py` — add `escalation_level`, `last_notified_at`

### Success Criteria

- [ ] No individual notifications for tasks < 3 days overdue
- [ ] Morning briefing sends at 7 AM
- [ ] 3+ tasks grouped into one message
- [ ] Buttons appear (even if not functional)

---

## Phase 2: Button Actions

**Goal:** Take action directly from Slack without switching apps.

### Deliverables

1. **Defer button**
   - Dropdown: Tomorrow, 3 days, 1 week, Pick date
   - Updates due date in source system (ClickUp/GitHub)

2. **Done button**
   - Opens thread: "What happened?"
   - User replies → marks complete with note

3. **Snooze button**
   - Hides locally without changing source
   - Dropdown: 1 day, 3 days, 1 week

4. **Delegate button** (basic)
   - Dropdown: Attila, Tamas
   - Reassigns in source system

### Files to Create/Modify

- `backend/app/slack_blocks.py` — interactive blocks
- `backend/app/slack_actions.py` — button handlers
- `backend/app/main.py` — Slack interaction endpoint
- `backend/app/models.py` — add `snooze_until`

### Success Criteria

- [ ] Defer updates due date in ClickUp/GitHub
- [ ] Done collects context via thread, marks complete
- [ ] Snooze hides task locally
- [ ] Delegate reassigns task

---

## Phase 3: AI Conversations

**Goal:** Natural language task management in Slack.

### Deliverables

1. **AI engine** (simple version)
   - Azure OpenAI (GPT-4/5) as primary
   - Regex fallback if AI fails
   - No complex fallback chain yet

2. **Task commands via NL**
   - "Defer Kyle stuff to next week"
   - "What's overdue?"
   - "Mark the proposal task done"

3. **Entity queries**
   - "What's happening with Kyle?"
   - "Show me Attila's blocked items"

4. **Basic research**
   - "Find co-working spaces in LA"
   - Web search + summarize

### Files to Create/Modify

- `backend/app/ai_engine.py` — AI provider abstraction
- `backend/app/intent_parser.py` — extract intent from NL
- `backend/app/bot.py` — replace regex with AI routing
- `backend/app/researcher.py` — web search + summarize

### Success Criteria

- [ ] "defer X to Monday" works via natural language
- [ ] "what's happening with Kyle" returns entity summary
- [ ] Research queries return useful summaries
- [ ] Graceful fallback when AI fails

---

## Phase 4: Context Layer

**Goal:** Bot knows where you are, what matters, what's scheduled.

### Deliverables

1. **Location tracking**
   - "I'm in LA until Feb 5"
   - Adjusts timezone for notifications
   - "I'm home" resets

2. **Priority overrides**
   - "Focus on investors this week"
   - Boosts/dampens task scores
   - Time-boxed (expires)

3. **Calendar integration**
   - Pulls today's events from Google Calendar
   - Pre-meeting reminders with context

4. **Status command**
   - Shows current context state
   - Location, priorities, snoozes

### Files to Create/Modify

- `backend/app/context.py` — context layer
- `~/.ivan/context.yaml` — location config
- `~/.ivan/priorities.yaml` — priority overrides
- `backend/app/calendar.py` — Google Calendar integration

### Success Criteria

- [ ] "I'm in LA" updates timezone
- [ ] "Focus on Kyle" boosts Kyle tasks
- [ ] Morning briefing shows today's calendar
- [ ] "status" shows current context

---

## Phase 5: Input Processing

**Goal:** Process any input — links, images, files.

### Deliverables

1. **Link processing**
   - Articles: fetch, summarize
   - YouTube: get transcript, summarize
   - Google Docs: read via integration

2. **Image processing**
   - GPT-4V vision analysis
   - Extract text, describe content
   - "Turn this whiteboard into tasks"

3. **File processing**
   - PDF: extract text, summarize
   - Other files: basic handling

4. **Voice memos** (if time)
   - Whisper transcription
   - Process as text

### Files to Create/Modify

- `backend/app/input_processor.py` — multi-modal input
- `backend/app/link_fetcher.py` — article/YouTube handling
- `backend/app/vision.py` — image analysis

### Success Criteria

- [ ] Paste a link → get summary
- [ ] Upload image → get description/extraction
- [ ] Upload PDF → get summary

---

## Phase 6: Advanced Features

**Goal:** Full chief of staff capabilities.

### Deliverables

1. **Task dependencies**
   - Detect "after X", "blocked by Y"
   - Track and query blockers
   - Auto-unblock when dependency done

2. **Smart delegation routing**
   - Attila → GitHub (technical)
   - Tamas → ClickUp (marketing)
   - Config-driven rules

3. **Video processing**
   - Extract audio → Whisper
   - Sample frames → vision
   - Combined summary

4. **Bilingual support**
   - Hungarian detection
   - Route to ivan-os for HU quality

5. **AI fallback chain**
   - Azure → ivan-os → Anthropic → regex
   - 30s timeout per provider

6. **Full audit trail**
   - Log every action
   - Queryable history

### Files to Create/Modify

- `backend/app/dependencies.py` — task dependencies
- `backend/app/routing.py` — delegation rules
- `backend/app/video_processor.py` — video handling
- `backend/app/action_logger.py` — audit trail
- `~/.ivan/routing.yaml` — routing config

### Success Criteria

- [ ] "What's blocking Kyle stuff?" works
- [ ] Delegation auto-routes to correct person/system
- [ ] Video upload → transcript + visual summary
- [ ] Hungarian messages get quality responses
- [ ] "What happened yesterday?" shows action log

---

## Recommended Order

```
Phase 1 (Smart Notifications)
    ↓
Phase 2 (Button Actions)
    ↓
Phase 3 (AI Conversations)
    ↓
Phase 4 (Context Layer)
    ↓
Phase 5 (Input Processing)
    ↓
Phase 6 (Advanced)
```

**Phases 1-2** = Core value (stop spam, enable actions)
**Phase 3** = AI assistant basics
**Phases 4-6** = Nice-to-have, can defer

---

## Effort Estimates

| Phase | Complexity | Rough Size |
|-------|------------|------------|
| 1 | Medium | ~500 lines |
| 2 | Medium | ~600 lines |
| 3 | High | ~800 lines |
| 4 | Medium | ~400 lines |
| 5 | High | ~700 lines |
| 6 | Very High | ~1200 lines |

**Recommendation:** Commit to Phases 1-3 first. Evaluate before continuing.
