---
id: phase-4f-event-notifications-design
title: Phase 4F - Event-driven Notifications Design
type: project
status: active
owner: ivan
created: 2026-01-28
updated: 2026-01-28
tags: [phase-4, notifications, events, design]
---

# Phase 4F: Event-driven Notifications Design

## Problem

Current behavior: Sync runs → task has high score → push notification.

This is noise. Ivan has many high-priority tasks. A notification without a trigger is useless. The same task triggers "Urgent Task Alert" repeatedly because it still has a high score.

## Solution

Notifications triggered by **events** (changes), not by scores (static state).

## Event Types & Triggers

| Event | Trigger ID | Detection | Threshold |
|-------|------------|-----------|-----------|
| Deadline approaching | `deadline_warning` | 24h and 2h before due_date | Exempt |
| Task overdue | `overdue` | due_date passed, not done | Exempt |
| Newly assigned | `assigned` | assignee changed to you | Applies |
| Status → blocked/urgent | `status_critical` | status changed to critical state | Applies |
| @mentioned anywhere | `mentioned` | your name/ID in new comment | Applies |
| New comment on your task | `comment_on_owned` | comment count increased (webhook only) | Applies |
| Blocker resolved | `blocker_resolved` | task you were blocked by → done | Applies |

**NOT triggers (removed):**
- Task has high score (static)
- Task synced with no changes
- Task still urgent (no delta)

## Configuration Schema

```yaml
# config/notifications.yaml

# Mode sets defaults when switched. Individual triggers override.
mode: focus  # focus | full | off

# Only notify if task.score >= this (0 = all)
# NOTE: deadline_warning and overdue ignore threshold (time-sensitive)
threshold: 500

triggers:
  deadline_warning: true   # ignores threshold
  overdue: true            # ignores threshold
  assigned: true
  status_critical: true
  mentioned: true
  comment_on_owned: false  # off by default (can be noisy)
  blocker_resolved: true

# Preset modes (applied when mode changes):
# focus: threshold=500, only deadline_warning, overdue, mentioned, blocker_resolved
# full: threshold=0, all triggers on
# off: all notifications disabled
```

**Defaults:** Conservative, less noise. `comment_on_owned` off by default.

**Mode vs Triggers:** Mode sets defaults when switched. Individual trigger settings override mode.

**Threshold:** Applies to most triggers. `deadline_warning` and `overdue` are exempt (time-sensitive).

**Config loading:** Load on startup with sensible defaults if file missing. Restart to apply changes (no hot-reload).

## Task State Tracking

Add `notification_state` JSON column to Task model:

```json
{
  "prev_status": "todo",
  "prev_assignee": "ivan",
  "last_deadline_notified": "2026-01-27",
  "last_comment_count": 3,
  "last_mentioned_at": null,
  "dedupe_keys": [
    "deadline_warning:clickup:123:24h",
    "assigned:clickup:123:assignee=ivan"
  ]
}
```

**Why JSON:** Notification tracking logic may evolve (new triggers, new thresholds). Isolating it from core Task fields improves maintainability.

**Dedupe keys:** Stored per-task. If task deleted, no need to track its keys.

## Detection Flow

### On Webhook (real-time)

```
Webhook received (GitHub/ClickUp)
  → Log: source, event_type, task_id (for reliability monitoring)
  → Parse event type (status change, new comment, etc.)
  → Check if it's a trigger event
  → Pass to NotificationFilter
  → If passes → send notification
  → On success → update task.notification_state
```

### On Sync (fallback + deadline detection)

```
Sync completes
  → For each task, compare current vs notification_state:
      - Status changed? → status_critical trigger
      - Assignee changed to me? → assigned trigger
      - Deadline within 24h/2h and not yet notified? → deadline_warning
      - Overdue and not yet notified today? → overdue
      - Task I was blocked by now done? → blocker_resolved
  → Pass events to NotificationFilter
  → Dedupe against events already handled via webhook
  → If passes → send notification
  → On success → update notification_state
```

### Deduplication

Key format: `{trigger}:{task_id}:{event_fingerprint}`

Examples:
- `status_critical:clickup:123:status=blocked`
- `deadline_warning:github:45:24h`
- `assigned:clickup:123:assignee=ivan`
- `mentioned:github:45:comment_id=999`

No time bucket. Same actual change = same key = deduped.

### Comment Detection

**MVP approach:** Webhook-only for comment triggers (`mentioned`, `comment_on_owned`).

Rationale: Current sync doesn't fetch comments. Adding comment count requires extra API calls per task. Missing a comment notification is annoying but not damaging (unlike missing deadline warnings).

Webhook arrivals are logged for reliability monitoring. If gaps appear, we can add sync-based comment detection later.

## Notification Message Format

Structure: `{emoji} *{trigger}*\n"{task.title}"\n{context}\n<{task.url}|View task>`

| Trigger | Format |
|---------|--------|
| `deadline_warning` | ⏰ *Deadline in 24h*<br>"Write proposal for Kyle"<br>Due: Tomorrow 5pm<br><url\|View task> |
| `overdue` | 🔴 *Overdue*<br>"Submit report"<br>Was due: Jan 27<br><url\|View task> |
| `assigned` | 📥 *Newly assigned to you*<br>"Review PR"<br>By: Tamas<br><url\|View task> |
| `status_critical` | 🚨 *Status changed to blocked*<br>"Deploy feature"<br><url\|View task> |
| `mentioned` | 💬 *You were mentioned*<br>"Client meeting prep"<br>By: Attila in comment<br><url\|View task> |
| `comment_on_owned` | 💬 *New comment on your task*<br>"Fix login bug"<br>By: Tamas<br><url\|View task> |
| `blocker_resolved` | ✅ *Blocker resolved*<br>"Wait for API access"<br>You can now proceed<br><url\|View task> |

Each message tells you **what happened**, **which task**, and **why you're being notified**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    config/notifications.yaml                │
│         (mode, threshold, per-trigger toggles)              │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  EventDetector                              │
│  - compare_state(task, notification_state) → list[Event]    │
│  - parse_webhook(payload) → Event                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   [Webhook]            [Sync]
   real-time            fallback
        │                   │
        └─────────┬─────────┘
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  NotificationFilter                          │
│  - check threshold (except deadline/overdue)                │
│  - check trigger enabled                                    │
│  - check dedupe key                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                  SlackNotifier                              │
│  - format message per trigger type                          │
│  - send → on success, update notification_state             │
└─────────────────────────────────────────────────────────────┘
```

**Separation of concerns:**
- EventDetector = "what happened"
- NotificationFilter = "should we notify"
- SlackNotifier = "how to notify"

## File Changes

**New files:**
- `config/notifications.yaml` — user config with defaults
- `backend/app/event_detector.py` — detect events from state diff + webhooks
- `backend/app/notification_filter.py` — apply config rules (mode, threshold, toggles, dedupe)

**Modified files:**
- `backend/app/models.py` — add `notification_state` JSON column to Task
- `backend/app/notifier.py` — new message formats per trigger, remove score-based logic
- `backend/app/main.py` — wire up EventDetector in sync + webhook handlers, remove score>=1000 logic

## Migration

1. Add `notification_state` column to Task (nullable JSON, defaults to `{}`)
2. Remove score-based notification logic from `scheduled_sync()`
3. Create default `config/notifications.yaml`
4. Update webhook handlers to pass events through new pipeline
5. Update sync to detect state changes and pass through pipeline

## Success Criteria

- [ ] No notification unless something CHANGED
- [ ] Notification includes WHY it was sent (the trigger)
- [ ] User can configure which triggers they want (per-trigger toggles)
- [ ] User can set threshold to filter low-priority events
- [ ] User can switch modes (focus/full/off) for quick control
- [ ] Deadline/overdue notifications fire regardless of threshold
- [ ] Same event via webhook + sync = single notification (dedupe works)
- [ ] Webhook arrivals logged for reliability monitoring
