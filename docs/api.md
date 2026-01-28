---
id: ivan-task-manager-api
title: Ivan Task Manager - API Reference
type: reference
status: active
owner: ivan
created: 2026-01-27
updated: 2026-01-27
tags: [api, rest, fastapi]
---

# API Reference

## Base URL

- Local: `http://localhost:8000`
- Production: `https://backend-production-7a52.up.railway.app`
- CLI default: Set via `IVAN_API_URL` environment variable

## Endpoints

### Health Check

```
GET /health
```

Returns service health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-27T10:30:00.000000"
}
```

---

### Get All Tasks

```
GET /tasks
```

Returns all open tasks assigned to Ivan, sorted by priority score (highest first).

**Response:**
```json
[
  {
    "id": "clickup:abc123",
    "source": "clickup",
    "title": "Review client proposal",
    "description": "...",
    "status": "todo",
    "assignee": "ivan",
    "due_date": "2026-01-27",
    "url": "https://app.clickup.com/t/abc123",
    "score": 1500,
    "is_revenue": true,
    "is_blocking": ["tamas"],
    "score_breakdown": {
      "total": 1500,
      "revenue": 1000,
      "blocking": 500,
      "blocking_count": 1,
      "urgency": 0,
      "urgency_level": 1,
      "urgency_label": "No deadline",
      "recency": 0
    }
  }
]
```

---

### Get Next Task

```
GET /next
```

Returns the highest priority task to work on. Also sets this as the "current task" for `/done` and `/skip` operations.

**Response:**
```json
{
  "task": { ... },
  "context": "Revenue task | Due today",
  "message": "Focus on: Review client proposal"
}
```

**Response (no tasks):**
```json
{
  "task": null,
  "context": null,
  "message": "No tasks in queue!"
}
```

---

### Mark Task Done

```
POST /done
```

Marks the current task as complete and returns the next task.

**Response:**
```json
{
  "success": true,
  "message": "Completed: Review client proposal",
  "next_task": { ... }
}
```

**Error (no current task):**
```
HTTP 400
{
  "detail": "No current task to complete"
}
```

---

### Skip Task

```
POST /skip
```

Skips the current task and returns the next one.

**Response:**
```json
{
  "success": true,
  "message": "Skipped: Review client proposal",
  "next_task": { ... }
}
```

---

### Force Sync

```
POST /sync
```

Triggers immediate sync from all sources (ClickUp, GitHub) with retry logic.

**Response:**
```json
{
  "success": true,
  "results": {
    "clickup": 12,
    "github": 5,
    "errors": []
  }
}
```

**Response (with errors):**
```json
{
  "success": true,
  "results": {
    "clickup": 0,
    "github": 5,
    "errors": ["ClickUp: Authentication failed - check API token"]
  }
}
```

---

### Morning Briefing

```
GET /morning
```

Returns morning briefing data with top 3 tasks and summary statistics.

**Response:**
```json
{
  "top_tasks": [
    {
      "title": "Review client proposal",
      "score": 1500,
      "url": "https://app.clickup.com/t/abc123",
      "breakdown": { ... }
    }
  ],
  "summary": {
    "total_tasks": 15,
    "overdue": 2,
    "due_today": 3,
    "blocking_count": 1,
    "blocking": ["tamas"]
  }
}
```

## Error Handling

All errors return JSON with a `detail` field:

```json
{
  "detail": "Error message here"
}
```

Common HTTP status codes:
- `200` - Success
- `400` - Bad request (e.g., no current task)
- `404` - Resource not found
- `500` - Internal server error

## Sync Error Categories

The sync endpoint categorizes errors for better debugging:

| Error Type | Description |
|------------|-------------|
| `auth_error` | Authentication failed - check API token |
| `permission_error` | Permission denied - check API permissions |
| `not_found` | Resource not found - check list/repo ID |
| `rate_limit` | Rate limit exceeded - will retry later |
| `timeout` | Request timed out - network may be slow |
| `connection_error` | Could not connect - check network |
| `server_error` | Server error - source may be down |
