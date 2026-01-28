"""Ivan Task Manager - FastAPI Application.

A unified task management system that aggregates tasks from ClickUp and GitHub,
provides intelligent prioritization, and delivers actionable notifications.
"""

import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session

from .config import get_settings
from .entity_loader import (
    get_entity,
    get_all_entities,
    load_entities,
    find_entity_by_name,
)
from .entity_mapper import map_task_to_entity
from .models import Task, CurrentTask, DigestState, init_db, get_db, SessionLocal
from .scorer import (
    score_and_sort_tasks,
    get_score_breakdown,
    get_score_breakdown_with_context,
    calculate_score_with_context,
)
from .syncer import sync_all_sources
from .notifier import SlackNotifier
from .writers import get_writer

# Bot is optional - only imported if slack_bolt is available
try:
    from .bot import start_bot

    BOT_AVAILABLE = True
except ImportError:
    BOT_AVAILABLE = False
    start_bot = None

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Scheduler for periodic tasks
scheduler = AsyncIOScheduler()
notifier = SlackNotifier()


# =============================================================================
# Helper Functions
# =============================================================================


def enrich_task_with_entity(task: Task) -> tuple[Task, dict]:
    """Add entity context to task and return enriched breakdown.

    Returns:
        Tuple of (task with updated score, enriched breakdown dict)
    """
    mapping = map_task_to_entity(task)
    if mapping:
        entity_id, workstream_id = mapping
        entity = get_entity(entity_id)
        workstream = (
            entity.get_workstream(workstream_id) if entity and workstream_id else None
        )
        if entity and not workstream:
            workstream = entity.get_active_workstream()

        # Recalculate score with entity context
        task.score = calculate_score_with_context(task, entity, workstream)
        breakdown = get_score_breakdown_with_context(task, entity, workstream)
    else:
        task.score = task.score or 0
        breakdown = get_score_breakdown(task)

    return task, breakdown


# =============================================================================
# Scheduled Jobs
# =============================================================================


async def scheduled_sync():
    """Hourly sync job."""
    logger.info("Running scheduled sync...")
    results = await sync_all_sources()
    logger.info(f"Sync complete: {results}")

    # Check for urgent tasks and send instant notifications
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )
        tasks = score_and_sort_tasks(tasks)

        for task in tasks:
            if task.score >= 1000:
                await notifier.send_instant_notification(task, "High priority task")
    finally:
        db.close()


async def hourly_digest_job():
    """Hourly digest job - sends updates for non-urgent tasks."""
    logger.info("Running hourly digest job...")

    db = SessionLocal()
    try:
        # Get or create digest state
        digest_state = db.query(DigestState).first()
        if not digest_state:
            digest_state = DigestState()
            db.add(digest_state)
            db.commit()
            # First run - don't send digest, just set baseline
            logger.info("First digest run - setting baseline")
            return

        last_digest = digest_state.last_digest_at

        # Find new tasks (created since last digest)
        new_tasks = (
            db.query(Task)
            .filter(
                Task.assignee == "ivan",
                Task.status != "done",
                Task.created_at > last_digest,
            )
            .all()
        )

        # Find updated tasks (updated since last digest, but created before)
        updated_tasks = (
            db.query(Task)
            .filter(
                Task.assignee == "ivan",
                Task.status != "done",
                Task.updated_at > last_digest,
                Task.created_at <= last_digest,
            )
            .all()
        )

        # Only send if there are updates
        if new_tasks or updated_tasks:
            await notifier.send_hourly_digest(new_tasks, updated_tasks)
            logger.info(
                f"Digest sent: {len(new_tasks)} new, {len(updated_tasks)} updated"
            )
        else:
            logger.info("No updates for digest")

        # Update last digest time
        digest_state.last_digest_at = datetime.utcnow()
        db.commit()

    finally:
        db.close()


async def morning_briefing_job():
    """Morning briefing job."""
    logger.info("Sending morning briefing...")

    # Sync first
    await sync_all_sources()

    # Get tasks
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )
        tasks = score_and_sort_tasks(tasks)
        await notifier.send_morning_briefing(tasks)
    finally:
        db.close()


# =============================================================================
# App Lifecycle
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    import asyncio

    # Startup
    logger.info("Starting Ivan Task Manager...")
    init_db()

    # Load entities
    entities_path = Path(settings.entities_dir)
    if not entities_path.is_absolute():
        # Relative to project root (parent of backend/)
        entities_path = Path(__file__).parent.parent.parent / settings.entities_dir
    load_entities(entities_path)
    logger.info(f"Loaded entities from {entities_path}")

    # Schedule jobs
    scheduler.add_job(
        scheduled_sync, "interval", minutes=settings.sync_interval_minutes
    )

    # Hourly digest job - runs every hour on the half-hour
    scheduler.add_job(hourly_digest_job, "cron", minute=30)

    # Parse morning briefing time
    hour, minute = map(int, settings.morning_briefing_time.split(":"))
    scheduler.add_job(morning_briefing_job, "cron", hour=hour, minute=minute)

    scheduler.start()
    logger.info("Scheduler started")

    # Initial sync
    await sync_all_sources()

    # Start Slack bot in background if app token is configured
    bot_task = None
    if BOT_AVAILABLE and settings.slack_app_token:
        logger.info("Starting Slack bot...")
        bot_task = asyncio.create_task(start_bot())
    elif not BOT_AVAILABLE:
        logger.warning("slack_bolt not installed - bot disabled")
    else:
        logger.warning("SLACK_APP_TOKEN not set - bot disabled")

    yield

    # Shutdown
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
    scheduler.shutdown()
    logger.info("Ivan Task Manager stopped")


app = FastAPI(
    title="Ivan Task Manager",
    description="Unified task management with intelligent prioritization",
    version="0.1.0",
    lifespan=lifespan,
)


# =============================================================================
# Pydantic Models
# =============================================================================


class TaskResponse(BaseModel):
    id: str
    source: str
    title: str
    description: Optional[str]
    status: str
    assignee: Optional[str]
    due_date: Optional[str]
    url: str
    score: int
    is_revenue: bool
    is_blocking: list[str]
    score_breakdown: dict

    class Config:
        from_attributes = True


class NextTaskResponse(BaseModel):
    task: Optional[TaskResponse]
    context: Optional[str]
    message: str


class ActionResponse(BaseModel):
    success: bool
    message: str
    next_task: Optional[TaskResponse]


class EntitySummaryResponse(BaseModel):
    id: str
    name: str
    type: str
    company: Optional[str]
    relationship_type: Optional[str]
    priority: int
    active_workstream: Optional[str]


class WorkstreamResponse(BaseModel):
    id: str
    name: str
    status: str
    deadline: Optional[str]
    milestone: Optional[str]
    revenue_potential: Optional[str]


class EntityDetailResponse(BaseModel):
    id: str
    name: str
    type: str
    created: str
    updated: str
    tags: list[str]
    company: Optional[str]
    email: Optional[str]
    linkedin: Optional[str]
    phone: Optional[str]
    relationship_type: Optional[str]
    priority: int
    intention: Optional[str]
    workstreams: list[WorkstreamResponse]
    channels: dict[str, str]
    context_summary: Optional[str]


class CommentRequest(BaseModel):
    text: str


class CreateTaskRequest(BaseModel):
    title: str
    description: Optional[str] = None
    entity_id: Optional[str] = None


class WriteResultResponse(BaseModel):
    success: bool
    message: str
    source_id: Optional[str] = None
    conflict: bool = False
    current_state: Optional[str] = None


# =============================================================================
# API Routes
# =============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/tasks", response_model=list[TaskResponse])
async def get_tasks(db: Session = Depends(get_db)):
    """Get all tasks sorted by priority score."""
    tasks = db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()

    # Enrich with entity context
    enriched = []
    for task in tasks:
        task, breakdown = enrich_task_with_entity(task)
        enriched.append((task, breakdown))

    # Sort by enriched score
    enriched.sort(key=lambda x: x[0].score, reverse=True)

    return [
        TaskResponse(
            id=t.id,
            source=t.source,
            title=t.title,
            description=t.description,
            status=t.status,
            assignee=t.assignee,
            due_date=t.due_date.isoformat() if t.due_date else None,
            url=t.url,
            score=t.score,
            is_revenue=t.is_revenue,
            is_blocking=t.is_blocking,
            score_breakdown=breakdown,
        )
        for t, breakdown in enriched
    ]


@app.get("/next", response_model=NextTaskResponse)
async def get_next_task(db: Session = Depends(get_db)):
    """Get the highest priority task to work on."""
    tasks = db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()

    if not tasks:
        return NextTaskResponse(task=None, context=None, message="No tasks in queue!")

    # Enrich with entity context and sort
    enriched = []
    for task in tasks:
        task, breakdown = enrich_task_with_entity(task)
        enriched.append((task, breakdown))
    enriched.sort(key=lambda x: x[0].score, reverse=True)

    task, breakdown = enriched[0]

    # Update current task tracker
    current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()
    if not current:
        current = CurrentTask(user_id="ivan")
        db.add(current)
    current.task_id = task.id
    current.started_at = datetime.utcnow()
    db.commit()

    # Build context
    context_parts = []
    if task.is_revenue:
        context_parts.append("Revenue task")
    if task.is_blocking:
        context_parts.append(f"Blocking: {', '.join(task.is_blocking)}")
    context_parts.append(breakdown["urgency_label"])
    if breakdown.get("entity_name"):
        context_parts.append(breakdown["entity_name"])

    return NextTaskResponse(
        task=TaskResponse(
            id=task.id,
            source=task.source,
            title=task.title,
            description=task.description,
            status=task.status,
            assignee=task.assignee,
            due_date=task.due_date.isoformat() if task.due_date else None,
            url=task.url,
            score=task.score,
            is_revenue=task.is_revenue,
            is_blocking=task.is_blocking,
            score_breakdown=breakdown,
        ),
        context=" | ".join(context_parts),
        message=f"Focus on: {task.title}",
    )


@app.post("/done", response_model=ActionResponse)
async def mark_done(db: Session = Depends(get_db)):
    """Mark current task as done and get next task."""
    current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

    if not current or not current.task_id:
        raise HTTPException(status_code=400, detail="No current task to complete")

    task = db.query(Task).filter(Task.id == current.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Current task not found")

    # Mark as done
    task.status = "done"
    task.updated_at = datetime.utcnow()

    # TODO: Update in source system (ClickUp/GitHub)

    # Get next task
    remaining = (
        db.query(Task)
        .filter(
            Task.status != "done",
            Task.assignee == "ivan",
            Task.id != task.id,
        )
        .all()
    )

    db.commit()

    next_task_response = None
    if remaining:
        # Enrich with entity context and sort
        enriched = []
        for t in remaining:
            t, breakdown = enrich_task_with_entity(t)
            enriched.append((t, breakdown))
        enriched.sort(key=lambda x: x[0].score, reverse=True)

        next_task, breakdown = enriched[0]
        current.task_id = next_task.id
        current.started_at = datetime.utcnow()
        db.commit()

        next_task_response = TaskResponse(
            id=next_task.id,
            source=next_task.source,
            title=next_task.title,
            description=next_task.description,
            status=next_task.status,
            assignee=next_task.assignee,
            due_date=next_task.due_date.isoformat() if next_task.due_date else None,
            url=next_task.url,
            score=next_task.score,
            is_revenue=next_task.is_revenue,
            is_blocking=next_task.is_blocking,
            score_breakdown=breakdown,
        )

    return ActionResponse(
        success=True,
        message=f"Completed: {task.title}",
        next_task=next_task_response,
    )


@app.post("/skip", response_model=ActionResponse)
async def skip_task(db: Session = Depends(get_db)):
    """Skip current task and get next one."""
    current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

    if not current or not current.task_id:
        raise HTTPException(status_code=400, detail="No current task to skip")

    skipped_task = db.query(Task).filter(Task.id == current.task_id).first()

    # Get next task (excluding current)
    remaining = (
        db.query(Task)
        .filter(
            Task.status != "done",
            Task.assignee == "ivan",
            Task.id != current.task_id,
        )
        .all()
    )

    if not remaining:
        return ActionResponse(success=True, message="No more tasks", next_task=None)

    # Enrich with entity context and sort
    enriched = []
    for t in remaining:
        t, breakdown = enrich_task_with_entity(t)
        enriched.append((t, breakdown))
    enriched.sort(key=lambda x: x[0].score, reverse=True)

    next_task, breakdown = enriched[0]

    current.task_id = next_task.id
    current.started_at = datetime.utcnow()
    db.commit()

    return ActionResponse(
        success=True,
        message=f"Skipped: {skipped_task.title if skipped_task else 'Unknown'}",
        next_task=TaskResponse(
            id=next_task.id,
            source=next_task.source,
            title=next_task.title,
            description=next_task.description,
            status=next_task.status,
            assignee=next_task.assignee,
            due_date=next_task.due_date.isoformat() if next_task.due_date else None,
            url=next_task.url,
            score=next_task.score,
            is_revenue=next_task.is_revenue,
            is_blocking=next_task.is_blocking,
            score_breakdown=breakdown,
        ),
    )


@app.post("/sync")
async def force_sync():
    """Force sync from all sources."""
    results = await sync_all_sources()
    return {"success": True, "results": results}


@app.get("/morning")
async def get_morning_briefing(db: Session = Depends(get_db)):
    """Get morning briefing data."""
    tasks = db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
    tasks = score_and_sort_tasks(tasks)

    top_3 = tasks[:3]
    overdue = sum(1 for t in tasks if t.due_date and t.due_date < datetime.now().date())
    due_today = sum(
        1 for t in tasks if t.due_date and t.due_date == datetime.now().date()
    )

    blocking = set()
    for t in tasks:
        blocking.update(t.is_blocking or [])

    return {
        "top_tasks": [
            {
                "title": t.title,
                "score": t.score,
                "url": t.url,
                "breakdown": get_score_breakdown(t),
            }
            for t in top_3
        ],
        "summary": {
            "total_tasks": len(tasks),
            "overdue": overdue,
            "due_today": due_today,
            "blocking_count": len(blocking),
            "blocking": list(blocking),
        },
    }


# =============================================================================
# Entity Routes
# =============================================================================


@app.get("/entities", response_model=list[EntitySummaryResponse])
async def list_entities():
    """List all entities with summary info."""
    entities = get_all_entities()
    return [
        EntitySummaryResponse(
            id=e.id,
            name=e.name,
            type=e.type,
            company=e.company,
            relationship_type=e.relationship_type,
            priority=e.get_priority(),
            active_workstream=(
                e.get_active_workstream().name if e.get_active_workstream() else None
            ),
        )
        for e in entities
    ]


@app.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity_detail(entity_id: str):
    """Get full entity details."""
    entity = get_entity(entity_id)
    if not entity:
        # Try fuzzy match
        entity = find_entity_by_name(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    return EntityDetailResponse(
        id=entity.id,
        name=entity.name,
        type=entity.type,
        created=entity.created.isoformat(),
        updated=entity.updated.isoformat(),
        tags=entity.tags,
        company=entity.company,
        email=entity.email,
        linkedin=entity.linkedin,
        phone=entity.phone,
        relationship_type=entity.relationship_type,
        priority=entity.get_priority(),
        intention=entity.intention,
        workstreams=[
            WorkstreamResponse(
                id=ws.id,
                name=ws.name,
                status=ws.status,
                deadline=ws.deadline.isoformat() if ws.deadline else None,
                milestone=ws.milestone,
                revenue_potential=ws.revenue_potential,
            )
            for ws in entity.workstreams
        ],
        channels=entity.channels,
        context_summary=entity.context_summary,
    )


@app.post("/entities/reload")
async def reload_entities():
    """Reload entities from YAML files."""
    entities_path = Path(settings.entities_dir)
    if not entities_path.is_absolute():
        entities_path = Path(__file__).parent.parent.parent / settings.entities_dir
    load_entities(entities_path)
    return {"message": f"Reloaded {len(get_all_entities())} entities"}


# =============================================================================
# Write API Routes (Bidirectional Sync)
# =============================================================================


@app.post("/tasks/{task_id}/complete", response_model=WriteResultResponse)
async def complete_task_in_source(task_id: str, db: Session = Depends(get_db)):
    """Mark task complete in its source system (ClickUp/GitHub)."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Extract source_id from task.id (format: "source:source_id")
    source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id

    writer = get_writer(task.source)
    result = await writer.complete(source_id)

    if result.success and not result.conflict:
        task.status = "done"
        task.updated_at = datetime.utcnow()
        db.commit()

    return WriteResultResponse(
        success=result.success,
        message=result.message,
        conflict=result.conflict,
        current_state=result.current_state,
    )


@app.post("/tasks/{task_id}/comment", response_model=WriteResultResponse)
async def add_comment_to_source(
    task_id: str, request: CommentRequest, db: Session = Depends(get_db)
):
    """Add comment to task in its source system."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    # Extract source_id from task.id (format: "source:source_id")
    source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id

    writer = get_writer(task.source)
    result = await writer.comment(source_id, request.text)

    return WriteResultResponse(
        success=result.success,
        message=result.message,
    )


@app.post("/tasks", response_model=WriteResultResponse)
async def create_task_in_source(
    request: CreateTaskRequest,
    source: str = "clickup",
):
    """Create new task in source system."""
    if source not in ["clickup", "github"]:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    writer = get_writer(source)
    result = await writer.create(
        title=request.title,
        description=request.description,
        entity_id=request.entity_id,
    )

    return WriteResultResponse(
        success=result.success,
        message=result.message,
        source_id=result.source_id,
    )


# =============================================================================
# Webhook Receivers (Real-time Updates)
# =============================================================================


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = (
        "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


def verify_clickup_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify ClickUp webhook signature."""
    if not secret:
        return True  # Skip verification if no secret configured
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhooks/github")
async def github_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle GitHub webhook events."""
    # Read body before parsing (for signature verification)
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = request.headers.get("X-GitHub-Event", "")
    action = payload.get("action", "")

    # Handle issue events
    if event == "issues":
        issue = payload.get("issue", {})
        issue_number = str(issue.get("number", ""))
        task_id = f"github:{issue_number}"

        task = db.query(Task).filter(Task.id == task_id).first()

        if action == "closed" and task:
            task.status = "done"
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"GitHub webhook: marked {task_id} as done")

        elif action == "reopened" and task:
            task.status = "todo"
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"GitHub webhook: reopened {task_id}")

        elif action == "edited" and task:
            task.title = issue.get("title", task.title)
            task.description = issue.get("body", task.description)
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"GitHub webhook: updated {task_id}")

    return {"status": "ok", "event": event, "action": action}


@app.post("/webhooks/clickup")
async def clickup_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle ClickUp webhook events."""
    # Read body before parsing (for signature verification)
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Signature", "")
    if not verify_clickup_signature(body, signature, settings.clickup_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event = payload.get("event", "")
    task_data = payload.get("task_id") or payload.get("task", {}).get("id")

    if not task_data:
        return {"status": "ok", "event": event, "message": "No task data"}

    task_id = f"clickup:{task_data}"
    task = db.query(Task).filter(Task.id == task_id).first()

    if event == "taskStatusUpdated" and task:
        history = payload.get("history_items", [{}])
        if history:
            new_status = history[0].get("after", {}).get("status", "")
            if new_status.lower() in ["complete", "closed", "done"]:
                task.status = "done"
            else:
                task.status = "todo"
            task.updated_at = datetime.utcnow()
            db.commit()
            logger.info(f"ClickUp webhook: {task_id} status -> {task.status}")

    elif event == "taskUpdated" and task:
        # General task update
        task.updated_at = datetime.utcnow()
        db.commit()
        logger.info(f"ClickUp webhook: updated {task_id}")

    return {"status": "ok", "event": event}
