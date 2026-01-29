# Task Queue

> **Read this file at session start.** Single source of truth for pending work.

## PENDING

### 1. [BUILD] Ticket Processor (Priority: High)

**Spec:** `docs/plans/2026-01-29-ticket-processor-implementation.md`

**Summary:** Implement Layer 4 execution capability that processes GitHub tickets, drafts responses, and creates actionable tasks.

**Key deliverables:**
- `action` field on Task model
- `processor.py` module (question detection, draft generation)
- `/process` and `/import` API endpoints
- `ivan process` and `ivan import` CLI commands
- Modified `ivan done` to execute actions
- Export/import for offline workflow

**12 tasks in spec.** Follow TDD approach - write failing test, implement, verify, commit.

---

## IN PROGRESS

(none)

---

## DONE

(none yet)

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
