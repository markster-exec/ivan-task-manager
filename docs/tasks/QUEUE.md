---
id: task-queue
title: Task Queue
type: reference
status: active
owner: ivan
created: 2026-01-29
updated: 2026-01-31
tags: [tasks, queue]
---

# Task Queue

> **Read this file at session start.** Single source of truth for pending work.

## PENDING

(none currently - evaluating Phase 1-3 results)

---

### FUTURE (After Phase 1-3 evaluation)

- Phase 4: Entity Awareness (entity queries, status summaries)
- Phase 5: Input Processing (links, images, files)
- Phase 6: Advanced (dependencies, routing, video, bilingual)

See `docs/plans/2026-01-31-chief-of-staff-phases.md` for details.

---

## IN PROGRESS

(none)

---

## DONE

### 1. [BUILD] Chief of Staff Bot — Phase 3: AI Conversations (Priority: Medium) — Completed 2026-01-31

**Spec:** `docs/plans/2026-01-31-phase3-ai-conversations-design.md`

**Summary:** Implemented AI-powered natural language task management with regex + AI hybrid approach.

**Deliverables completed:**
- ✓ AI engine with Azure OpenAI (timeout, fallback, JSON parsing)
- ✓ Intent parser (regex for fast matching, AI for complex queries)
- ✓ Web research (DuckDuckGo + AI summarization)
- ✓ NL task commands ("defer X to Monday")
- ✓ Entity queries ("what's happening with Kyle?")
- ✓ 36 new tests (all passing)

**Files created:**
- `backend/app/ai_engine.py`
- `backend/app/intent_parser.py`
- `backend/app/researcher.py`
- `backend/tests/test_ai_engine.py`
- `backend/tests/test_intent_parser.py`
- `backend/tests/test_researcher.py`
- `docs/plans/2026-01-31-phase3-ai-conversations-design.md`

**Files modified:**
- `backend/app/bot.py` (AI-powered routing + new handlers)

---

### 2. [BUILD] Chief of Staff Bot — Phase 2: Button Actions (Priority: Medium) — Completed 2026-01-31

**Spec:** `docs/plans/2026-01-31-phase2-button-actions-design.md`

**Summary:** Implemented interactive Slack buttons that take action directly without switching apps.

**Deliverables completed:**
- ✓ Defer button → modal with date options, updates source system
- ✓ Done button → modal with context input, marks complete
- ✓ Snooze button → hides task locally (snooze_until column)
- ✓ Delegate button → reassigns to Attila/Tamas in source system
- ✓ Writer methods: `update_due_date()`, `reassign()`
- ✓ Alembic migration 002 for snooze_until column
- ✓ 24 new tests (all passing)

**Files created:**
- `backend/app/slack_actions.py`
- `backend/alembic/versions/002_add_snooze_until.py`
- `backend/tests/test_slack_actions.py`
- `docs/plans/2026-01-31-phase2-button-actions-design.md`

**Files modified:**
- `backend/app/models.py` (added snooze_until)
- `backend/app/writers/base.py`, `clickup.py`, `github.py`
- `backend/app/slack_blocks.py` (real buttons + modals)
- `backend/app/bot.py` (registers handlers)
- `backend/tests/test_writers.py`

---

### 3. [BUILD] Chief of Staff Bot — Phase 1: Smart Notifications (Priority: High) — Completed 2026-01-31

**Spec:** `docs/plans/2026-01-31-chief-of-staff-phases.md` (Phase 1 section)

**Summary:** Implemented smart escalation notifications that replace spam with consolidated, escalated alerts.

**Deliverables completed:**
- ✓ Escalation ladder (day 0/1/2/3+/5+/7+) in `escalation.py`
- ✓ Morning briefing generator in `briefing.py` (top 3, stats, calendar placeholder)
- ✓ Consolidation rule (3+ tasks → one grouped message)
- ✓ Placeholder buttons [Defer] [Done] [Snooze] in `slack_blocks.py`
- ✓ `user_timezone` config setting (currently: America/Los_Angeles)
- ✓ Model columns: `escalation_level`, `last_notified_at`
- ✓ Alembic migration for new columns
- ✓ 40 new tests (all passing)

**Files created:**
- `backend/app/escalation.py`
- `backend/app/briefing.py`
- `backend/alembic/versions/001_add_escalation_columns.py`
- `backend/tests/test_escalation.py`
- `backend/tests/test_briefing.py`

**Files modified:**
- `backend/app/config.py` (added user_timezone)
- `backend/app/models.py` (added escalation columns)
- `backend/app/slack_blocks.py` (added buttons and escalation formatting)
- `backend/app/notifier.py` (added escalation notification methods)

---

### 4. [BUILD] Ticket Processor (Priority: High) — Completed 2026-01-30

**Spec:** `docs/plans/2026-01-29-ticket-processor-implementation.md`

**Summary:** Implemented Layer 4 execution capability that processes GitHub tickets, drafts responses, and creates actionable tasks.

**Deliverables completed:**
- ✓ `action` field on Task model
- ✓ `processor.py` module (question detection, draft generation)
- ✓ `/process` and `/import` API endpoints
- ✓ `ivan process` and `ivan import` CLI commands
- ✓ Modified `ivan done` to execute actions
- ✓ `ivan done -e` to edit before posting
- ✓ Export/import for offline workflow

**12/12 tasks complete.**

---

## How to Use

**ivan2 at session start:**
1. Read `STATE.md` for current position
2. Read this file for pending tasks
3. If PENDING tasks exist, work on them in priority order

**When starting a task:**
1. Move from PENDING to IN PROGRESS
2. Read the full spec file in `docs/tasks/`
3. Implement

**When done:**
1. Move to DONE with completion date
2. Update STATE.md
