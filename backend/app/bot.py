"""Slack bot listener using Socket Mode.

Listens for DMs and responds to commands like:
- "next" / "what should I work on?"
- "done" / "finished"
- "skip" / "later"
- "tasks" / "show my tasks"
- "morning" / "briefing"
- "sync" / "refresh"
- Natural language commands via AI
- Research queries
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from .config import get_settings
from .models import Task, CurrentTask, SessionLocal
from .scorer import score_and_sort_tasks, get_score_breakdown
from .syncer import sync_all_sources
from .entity_loader import find_entity_by_name, get_all_entities
from .writers import get_writer
from .intent_parser import get_intent_parser
from .researcher import get_researcher
from . import slack_blocks

settings = get_settings()
logger = logging.getLogger(__name__)


# =============================================================================
# Command Handlers
# =============================================================================


async def handle_next(user_id: str) -> dict:
    """Get the next highest priority task.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return {"text": "✅ No tasks in queue! Enjoy your free time."}

        tasks = score_and_sort_tasks(tasks)
        task = tasks[0]

        # Update current task tracker
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()
        if not current:
            current = CurrentTask(user_id="ivan")
            db.add(current)
        current.task_id = task.id
        db.commit()

        # Build response
        breakdown = get_score_breakdown(task)
        flags = []
        if task.is_revenue:
            flags.append("💰 Revenue")
        if task.is_blocking:
            flags.append(f"🚫 Blocking: {', '.join(task.is_blocking)}")
        flags.append(f"⏰ {breakdown['urgency_label']}")

        desc = task.description or "No description"

        text, blocks = slack_blocks.format_next_task(
            title=task.title,
            url=task.url,
            score=task.score,
            flags=flags,
            description=desc,
        )

        return {"text": text, "blocks": blocks}

    finally:
        db.close()


async def handle_done(user_id: str) -> dict:
    """Mark current task as done in source system.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

        if not current or not current.task_id:
            return {"text": '❓ No current task. Say "next" to get one.'}

        task = db.query(Task).filter(Task.id == current.task_id).first()
        if not task:
            return {"text": '❓ Current task not found. Say "next" to get a new one.'}

        completed_title = task.title
        completed_url = task.url

        # Write to source system (ClickUp/GitHub)
        source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
        writer = get_writer(task.source)
        result = await writer.complete(source_id)

        if not result.success:
            return {"text": f"❌ Failed to complete in {task.source}: {result.message}"}

        # Mark as done locally
        task.status = "done"
        db.commit()

        # Get next task
        next_response = await handle_next(user_id)
        completion_text, completion_blocks = slack_blocks.format_completion(
            completed_title, completed_url
        )

        # Add conflict note if task was already done externally
        if result.conflict:
            completion_blocks.append(
                slack_blocks.context(f"ℹ️ Task was already completed in {task.source}")
            )

        # Combine completion + next task blocks
        blocks = completion_blocks + [slack_blocks.divider()]
        if "blocks" in next_response:
            blocks.extend(next_response["blocks"])

        return {
            "text": f"{completion_text}\n\n{next_response['text']}",
            "blocks": blocks,
        }

    finally:
        db.close()


async def handle_comment(user_id: str, comment_text: str) -> dict:
    """Add comment to current task in source system.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

        if not current or not current.task_id:
            return {"text": '❓ No current task. Say "next" to get one first.'}

        task = db.query(Task).filter(Task.id == current.task_id).first()
        if not task:
            return {"text": '❓ Current task not found. Say "next" to get a new one.'}

        # Write comment to source system (ClickUp/GitHub)
        source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
        writer = get_writer(task.source)
        result = await writer.comment(source_id, comment_text)

        if not result.success:
            return {
                "text": f"❌ Failed to add comment to {task.source}: {result.message}"
            }

        text = f"💬 Comment added to *{task.title}*"
        blocks = [
            slack_blocks.section(f"💬 Comment added to <{task.url}|{task.title}>"),
            slack_blocks.context(f'"{comment_text}"'),
        ]

        return {"text": text, "blocks": blocks}

    finally:
        db.close()


async def handle_skip(user_id: str) -> dict:
    """Skip current task and get next one.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

        if not current or not current.task_id:
            return {"text": '❓ No current task to skip. Say "next" to get one.'}

        skipped = db.query(Task).filter(Task.id == current.task_id).first()
        skipped_title = skipped.title if skipped else "Unknown"

        # Get remaining tasks (excluding current)
        tasks = (
            db.query(Task)
            .filter(
                Task.status != "done",
                Task.assignee == "ivan",
                Task.id != current.task_id,
            )
            .all()
        )

        if not tasks:
            skip_text, skip_blocks = slack_blocks.format_skip(skipped_title)
            skip_blocks.append(slack_blocks.context("No more tasks in queue."))
            return {
                "text": f"{skip_text}\n\nNo more tasks in queue.",
                "blocks": skip_blocks,
            }

        tasks = score_and_sort_tasks(tasks)
        next_task = tasks[0]
        current.task_id = next_task.id
        db.commit()

        # Build response
        breakdown = get_score_breakdown(next_task)
        flags = []
        if next_task.is_revenue:
            flags.append("💰 Revenue")
        if next_task.is_blocking:
            flags.append(f"🚫 Blocking: {', '.join(next_task.is_blocking)}")
        flags.append(f"⏰ {breakdown['urgency_label']}")

        skip_text, skip_blocks = slack_blocks.format_skip(skipped_title)
        next_text, next_blocks = slack_blocks.format_next_task(
            title=next_task.title,
            url=next_task.url,
            score=next_task.score,
            flags=flags,
            description=next_task.description or "No description",
        )

        blocks = skip_blocks + [slack_blocks.divider()] + next_blocks

        return {
            "text": f"{skip_text}\n\n{next_text}",
            "blocks": blocks,
        }

    finally:
        db.close()


async def handle_tasks(user_id: str) -> dict:
    """Show all tasks sorted by priority.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return {"text": "✅ No tasks in queue!"}

        tasks = score_and_sort_tasks(tasks)

        # Prepare data for Block Kit formatter
        tasks_data = []
        for task in tasks[:10]:
            breakdown = get_score_breakdown(task)
            emoji = "🔴" if task.score >= 1000 else "🟡" if task.score >= 500 else "🟢"
            tasks_data.append(
                {
                    "title": task.title,
                    "url": task.url,
                    "score": task.score,
                    "urgency_label": breakdown["urgency_label"],
                    "emoji": emoji,
                }
            )

        text, blocks = slack_blocks.format_task_list(tasks_data, len(tasks))
        return {"text": text, "blocks": blocks}

    finally:
        db.close()


async def handle_morning(user_id: str) -> dict:
    """Get morning briefing.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return {"text": "☀️ *Good morning!*\n\nNo tasks in queue. Enjoy your day!"}

        tasks = score_and_sort_tasks(tasks)

        # Prepare focus tasks data
        focus_tasks = []
        for task in tasks[:3]:
            breakdown = get_score_breakdown(task)
            flags = []
            if task.is_revenue:
                flags.append("💰 Revenue")
            if task.is_blocking:
                flags.append(f"🚫 Blocking: {', '.join(task.is_blocking)}")
            flags.append(f"⏰ {breakdown['urgency_label']}")

            focus_tasks.append(
                {
                    "title": task.title,
                    "url": task.url,
                    "score": task.score,
                    "flags": flags,
                }
            )

        # Stats
        from .scorer import get_urgency_label

        overdue = sum(1 for t in tasks if get_urgency_label(t.due_date) == "Overdue")
        due_today = sum(
            1 for t in tasks if get_urgency_label(t.due_date) == "Due today"
        )
        blocking = set()
        for t in tasks:
            blocking.update(t.is_blocking or [])

        stats = {
            "total": len(tasks),
            "overdue": overdue,
            "due_today": due_today,
            "blocking_count": len(blocking),
        }

        text, blocks = slack_blocks.format_morning_briefing(focus_tasks, stats)
        return {"text": text, "blocks": blocks}

    finally:
        db.close()


async def handle_sync(user_id: str) -> dict:
    """Force sync from all sources.

    Returns:
        dict with 'text' (fallback) and optional 'blocks' (Block Kit)
    """
    try:
        results = await sync_all_sources()
        text = f"🔄 Sync complete! ClickUp: {results.get('clickup', 0)}, GitHub: {results.get('github', 0)}"
        blocks = [
            slack_blocks.section("🔄 *Sync complete!*"),
            slack_blocks.context(
                f"• ClickUp: {results.get('clickup', 0)} tasks\n"
                f"• GitHub: {results.get('github', 0)} tasks"
            ),
            slack_blocks.context('Say "tasks" to see updated list.'),
        ]
        return {"text": text, "blocks": blocks}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {"text": f"❌ Sync failed: {str(e)}"}


async def handle_help(user_id: str) -> dict:
    """Show available commands.

    Returns:
        dict with 'text' (fallback) and 'blocks' (Block Kit)
    """
    text = "👋 Ivan Task Manager - Commands: next, done, skip, comment, tasks, morning, sync, help"
    blocks = [
        slack_blocks.section("👋 *Ivan Task Manager*"),
        slack_blocks.divider(),
        slack_blocks.section(
            "*Commands:*\n"
            "• *next* - Get your highest priority task\n"
            "• *done* - Mark current task complete\n"
            "• *skip* - Skip to next task\n"
            "• *comment <text>* - Add comment to current task\n"
            "• *tasks* - Show all your tasks\n"
            "• *morning* - Get morning briefing\n"
            "• *sync* - Refresh from ClickUp/GitHub\n"
            "• *help* - Show this message"
        ),
        slack_blocks.divider(),
        slack_blocks.context(
            "You can also ask naturally:\n"
            '• "What should I work on?"\n'
            '• "I finished the task"\n'
            '• "Show me my tasks"'
        ),
    ]
    return {"text": text, "blocks": blocks}


async def handle_entity(user_id: str, entity_name: str) -> dict:
    """Get entity information.

    Returns:
        dict with 'text' and 'blocks'
    """
    entity = find_entity_by_name(entity_name)
    if not entity:
        return {"text": f"Entity '{entity_name}' not found."}

    # Build response
    text = f"*{entity.name}* — {entity.company or 'N/A'}"

    blocks = [
        slack_blocks.section(f"*{entity.name}* — {entity.company or 'N/A'}"),
    ]

    if entity.intention:
        blocks.append(slack_blocks.context(f"Intention: {entity.intention}"))

    # Priority stars
    priority_stars = "*" * entity.get_priority()
    blocks.append(
        slack_blocks.context(
            f"Priority: {priority_stars} ({entity.relationship_type or 'unset'})"
        )
    )

    # Active workstream
    active_ws = entity.get_active_workstream()
    if active_ws:
        deadline = f" — due {active_ws.deadline}" if active_ws.deadline else ""
        blocks.append(slack_blocks.section(f"*Active:* {active_ws.name}{deadline}"))

    # Channels
    if entity.channels:
        channel_links = []
        for key, value in entity.channels.items():
            if key == "gdoc":
                url = f"https://docs.google.com/document/d/{value}"
            elif key == "github" and not value.startswith("http"):
                url = f"https://github.com/{value}"
            else:
                url = value
            channel_links.append(f"<{url}|{key.capitalize()}>")
        blocks.append(slack_blocks.context(" | ".join(channel_links)))

    return {"text": text, "blocks": blocks}


async def handle_projects(user_id: str) -> dict:
    """List all entities with active workstreams.

    Returns:
        dict with 'text' and 'blocks'
    """
    entities = get_all_entities()
    active = [e for e in entities if e.get_active_workstream()]

    if not active:
        return {"text": "No active workstreams."}

    text = "Active Workstreams"
    blocks = [slack_blocks.section("*Active Workstreams*"), slack_blocks.divider()]

    for entity in sorted(active, key=lambda e: -e.get_priority()):
        ws = entity.get_active_workstream()
        deadline = f" — due {ws.deadline}" if ws.deadline else ""
        blocks.append(
            slack_blocks.section(
                f"*{entity.name}* ({entity.company or 'N/A'})\n-> {ws.name}{deadline}"
            )
        )

    return {"text": text, "blocks": blocks}


async def handle_defer_nl(user_id: str, params: dict) -> dict:
    """Handle natural language defer command.

    Args:
        user_id: Slack user ID
        params: Parsed parameters (entity?, days?)

    Returns:
        dict with 'text' and 'blocks'
    """
    entity_name = params.get("entity")
    days = params.get("days", 7)

    db = SessionLocal()
    try:
        query = db.query(Task).filter(Task.status != "done", Task.assignee == "ivan")

        tasks_to_defer = []

        # Filter by entity if specified
        if entity_name:
            entity = find_entity_by_name(entity_name)
            if not entity:
                return {"text": f"Entity '{entity_name}' not found."}

            # Find tasks matching entity (check title for entity reference)
            all_tasks = query.all()
            entity_lower = entity_name.lower()
            for task in all_tasks:
                title_lower = task.title.lower()
                if entity_lower in title_lower or entity.name.lower() in title_lower:
                    tasks_to_defer.append(task)

            if not tasks_to_defer:
                return {"text": f"No tasks found related to {entity.name}."}
        else:
            # No entity specified - defer current task only
            current = (
                db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()
            )
            if not current or not current.task_id:
                return {"text": 'No current task. Say "next" to get one.'}

            task = db.query(Task).filter(Task.id == current.task_id).first()
            if task:
                tasks_to_defer = [task]
            else:
                return {"text": "Current task not found."}

        # Calculate new due date
        new_date = (datetime.now() + timedelta(days=days)).date()

        # Defer matching tasks
        deferred_count = 0
        for task in tasks_to_defer:
            source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
            writer = get_writer(task.source)
            result = await writer.update_due_date(source_id, new_date)

            if result.success:
                task.due_date = new_date
                task.escalation_level = 0
                deferred_count += 1

        db.commit()

        if entity_name:
            text = f"Deferred {deferred_count} {entity_name} task(s) to {new_date}"
        else:
            text = f"Deferred to {new_date}"

        return {
            "text": text,
            "blocks": [slack_blocks.section(f"📅 {text}")],
        }

    finally:
        db.close()


async def handle_research(user_id: str, query: str) -> dict:
    """Handle research query.

    Args:
        user_id: Slack user ID
        query: Search query

    Returns:
        dict with 'text' and 'blocks'
    """
    researcher = get_researcher()
    summary = await researcher.research(query)

    return {
        "text": summary,
        "blocks": [
            slack_blocks.section(f"🔍 *Research: {query}*"),
            slack_blocks.divider(),
            slack_blocks.section(summary),
        ],
    }


# =============================================================================
# Message Router
# =============================================================================

# Command patterns for backwards compatibility (fast regex path)
COMMAND_PATTERNS = [
    (r"\b(next|what should i (work on|do)|what'?s next)\b", handle_next),
    (r"\b(done|finished|completed|i finished)\b", handle_done),
    (r"\b(skip|later|not now)\b", handle_skip),
    (r"\b(tasks|show (my )?tasks|list|todo)\b", handle_tasks),
    (r"\b(morning|briefing|brief me)\b", handle_morning),
    (r"\b(sync|refresh|update)\b", handle_sync),
    (r"\b(projects|workstreams)\b", handle_projects),
    (r"\b(help|commands|\?)\b", handle_help),
]

# Intent handlers mapping
INTENT_HANDLERS = {
    "next": lambda uid, params: handle_next(uid),
    "done": lambda uid, params: handle_done(uid),
    "skip": lambda uid, params: handle_skip(uid),
    "tasks": lambda uid, params: handle_tasks(uid),
    "morning": lambda uid, params: handle_morning(uid),
    "sync": lambda uid, params: handle_sync(uid),
    "projects": lambda uid, params: handle_projects(uid),
    "help": lambda uid, params: handle_help(uid),
    "defer": lambda uid, params: handle_defer_nl(uid, params),
    "entity_query": lambda uid, params: handle_entity(
        uid, params.get("entity_name", "")
    ),
    "research": lambda uid, params: handle_research(uid, params.get("query", "")),
}


async def route_message(text: str, user_id: str) -> Optional[dict]:
    """Route message to appropriate handler using AI-powered intent parsing.

    Returns:
        dict with 'text' and optional 'blocks', or None if no match
    """
    # Check for comment command first (special: takes argument, keep regex)
    comment_match = re.match(r"comment\s+(.+)", text.strip(), re.IGNORECASE)
    if comment_match:
        comment_text = comment_match.group(1).strip()
        return await handle_comment(user_id, comment_text)

    # Use AI-powered intent parser
    parser = get_intent_parser()
    parsed = await parser.parse(text)

    logger.info(f"Parsed intent: {parsed.intent} (confidence: {parsed.confidence})")

    # Route to handler
    if parsed.intent in INTENT_HANDLERS:
        handler = INTENT_HANDLERS[parsed.intent]
        return await handler(user_id, parsed.params)

    # Unknown intent
    return None


# =============================================================================
# Bot Runner
# =============================================================================


def create_app():
    """Create and configure the Slack Bolt app."""
    from slack_bolt.async_app import AsyncApp

    from .slack_actions import register_action_handlers

    bolt_app = AsyncApp(token=settings.slack_bot_token)

    # Register interactive component handlers (buttons, modals)
    register_action_handlers(bolt_app)

    @bolt_app.event("message")
    async def handle_message_events(event: dict, say):
        """Handle incoming messages."""
        # Ignore bot messages
        if event.get("bot_id"):
            return

        # Only respond to DMs (channel type "im")
        if event.get("channel_type") != "im":
            return

        text = event.get("text", "")
        user_id = event.get("user", "")

        # Get thread_ts to reply in same thread (use thread_ts if in thread, else ts)
        thread_ts = event.get("thread_ts") or event.get("ts")

        logger.info(f"Received DM from {user_id}: {text}")

        response = await route_message(text, user_id)

        if response:
            # Send with Block Kit if available
            await say(
                text=response.get("text", ""),
                blocks=response.get("blocks"),
                thread_ts=thread_ts,
            )
        else:
            # Unknown command - show help
            help_response = await handle_help(user_id)
            await say(
                text="🤔 I didn't understand that. Here's what I can do:",
                blocks=[
                    slack_blocks.section(
                        "🤔 I didn't understand that. Here's what I can do:"
                    )
                ]
                + help_response.get("blocks", []),
                thread_ts=thread_ts,
            )

    @bolt_app.event("app_mention")
    async def handle_app_mention(event: dict, say):
        """Handle @mentions in channels."""
        text = event.get("text", "")
        user_id = event.get("user", "")

        # Get thread_ts to reply in same thread (use thread_ts if in thread, else ts)
        thread_ts = event.get("thread_ts") or event.get("ts")

        # Remove the mention itself
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        logger.info(f"Mentioned by {user_id}: {text}")

        response = await route_message(text, user_id)

        if response:
            # Send with Block Kit if available
            await say(
                text=response.get("text", ""),
                blocks=response.get("blocks"),
                thread_ts=thread_ts,
            )
        else:
            await say(
                text='👋 DM me for task management! Say "help" to see commands.',
                thread_ts=thread_ts,
            )

    return bolt_app


async def start_bot():
    """Start the Slack bot."""
    if not settings.slack_bot_token:
        logger.error("SLACK_BOT_TOKEN not set - bot cannot start")
        return

    if not settings.slack_app_token:
        logger.error("SLACK_APP_TOKEN not set - bot cannot start")
        return

    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

    logger.info("Starting Slack bot in Socket Mode...")
    bolt_app = create_app()
    handler = AsyncSocketModeHandler(bolt_app, settings.slack_app_token)
    await handler.start_async()


def run_bot():
    """Run the bot (blocking)."""
    asyncio.run(start_bot())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
