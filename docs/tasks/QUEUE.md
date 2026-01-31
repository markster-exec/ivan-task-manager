# Task Queue

> **Read this file at session start.** Single source of truth for pending work.

## PENDING

### 1. [BUILD] Chief of Staff Bot — Phase 1: Smart Notifications (Priority: High)

**Spec:** `docs/plans/2026-01-31-chief-of-staff-phases.md` (Phase 1 section)
**Full design:** `docs/plans/2026-01-31-chief-of-staff-bot-design.md`

**Goal:** Replace notification spam with consolidated, escalated alerts.

**Deliverables:**
- [ ] Escalation ladder (day 0/1/2/3+/5+/7+)
- [ ] Morning briefing (top 3 tasks, summary, calendar) at 7 AM
- [ ] Consolidation rule (3+ tasks → one grouped message)
- [ ] Basic buttons (defer, done, snooze) — placeholders, non-functional

**Files to create/modify:**
- `backend/app/escalation.py`
- `backend/app/briefing.py`
- `backend/app/notifier.py`
- `backend/app/models.py` (add escalation_level, last_notified_at)

**Success criteria:**
- No individual notifications for tasks < 3 days overdue
- Morning briefing sends at 7 AM local time
- 3+ tasks grouped into one message

---

### 2. [BUILD] Chief of Staff Bot — Phase 2: Button Actions (Priority: Medium)

**Spec:** `docs/plans/2026-01-31-chief-of-staff-phases.md` (Phase 2 section)

**Blocked by:** Phase 1

**Goal:** Take action directly from Slack buttons.

**Deliverables:**
- [ ] Defer button (dropdown: tomorrow, 3 days, 1 week, pick date)
- [ ] Done button (thread flow: "What happened?" → mark complete)
- [ ] Snooze button (hide locally)
- [ ] Delegate button (Attila, Tamas dropdown)

---

### 3. [BUILD] Chief of Staff Bot — Phase 3: AI Conversations (Priority: Medium)

**Spec:** `docs/plans/2026-01-31-chief-of-staff-phases.md` (Phase 3 section)

**Blocked by:** Phase 2

**Goal:** Natural language task management.

**Deliverables:**
- [ ] AI engine (Azure OpenAI + regex fallback)
- [ ] NL task commands ("defer X to Monday")
- [ ] Entity queries ("what's happening with Kyle?")
- [ ] Basic research ("find coworking spaces in LA")

---

### FUTURE (After Phase 1-3 evaluation)

- Phase 4: Context Layer (location, priorities, calendar)
- Phase 5: Input Processing (links, images, files)
- Phase 6: Advanced (dependencies, routing, video, bilingual)

See `docs/plans/2026-01-31-chief-of-staff-phases.md` for details.

---

## IN PROGRESS

(none)

---

## DONE

### 1. [BUILD] Ticket Processor (Priority: High) — Completed 2026-01-30

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
