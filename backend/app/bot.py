"""Slack bot listener using Socket Mode.

Listens for DMs and responds to commands like:
- "next" / "what should I work on?"
- "done" / "finished"
- "skip" / "later"
- "tasks" / "show my tasks"
- "morning" / "briefing"
- "sync" / "refresh"
"""

import asyncio
import logging
import re
from typing import Optional

from .config import get_settings
from .models import Task, CurrentTask, SessionLocal
from .scorer import score_and_sort_tasks, get_score_breakdown
from .syncer import sync_all_sources
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
    """Mark current task as done.

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

        # Mark as done
        task.status = "done"
        completed_title = task.title
        db.commit()

        # Get next task
        next_response = await handle_next(user_id)
        completion_text, completion_blocks = slack_blocks.format_completion(completed_title)

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
            return {"text": f"{skip_text}\n\nNo more tasks in queue.", "blocks": skip_blocks}

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
            tasks_data.append({
                "title": task.title,
                "url": task.url,
                "score": task.score,
                "urgency_label": breakdown["urgency_label"],
                "emoji": emoji,
            })

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

            focus_tasks.append({
                "title": task.title,
                "url": task.url,
                "score": task.score,
                "flags": flags,
            })

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
    text = "👋 Ivan Task Manager - Commands: next, done, skip, tasks, morning, sync, help"
    blocks = [
        slack_blocks.section("👋 *Ivan Task Manager*"),
        slack_blocks.divider(),
        slack_blocks.section(
            "*Commands:*\n"
            "• *next* - Get your highest priority task\n"
            "• *done* - Mark current task complete\n"
            "• *skip* - Skip to next task\n"
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


# =============================================================================
# Message Router
# =============================================================================

# Command patterns (case-insensitive)
COMMAND_PATTERNS = [
    (r"\b(next|what should i (work on|do)|what'?s next)\b", handle_next),
    (r"\b(done|finished|completed|i finished)\b", handle_done),
    (r"\b(skip|later|not now)\b", handle_skip),
    (r"\b(tasks|show (my )?tasks|list|todo)\b", handle_tasks),
    (r"\b(morning|briefing|brief me)\b", handle_morning),
    (r"\b(sync|refresh|update)\b", handle_sync),
    (r"\b(help|commands|\?)\b", handle_help),
]

# Intent handlers for Azure OpenAI classification
INTENT_HANDLERS = {
    "next": handle_next,
    "done": handle_done,
    "skip": handle_skip,
    "tasks": handle_tasks,
    "morning": handle_morning,
    "sync": handle_sync,
    "help": handle_help,
}


async def classify_intent_with_ai(text: str) -> Optional[str]:
    """Use Azure OpenAI to classify intent when regex fails.

    Returns one of: next, done, skip, tasks, morning, sync, help, or None.
    """
    if not settings.azure_openai_api_key:
        return None

    try:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version="2024-02-15-preview",
            azure_endpoint=settings.azure_openai_endpoint,
        )

        prompt = f"""Classify the following message into one of these task management intents:
- "next": User wants to get their next task to work on
- "done": User has completed their current task
- "skip": User wants to skip/defer the current task
- "tasks": User wants to see all their tasks
- "morning": User wants a morning briefing/summary
- "sync": User wants to refresh/sync tasks from sources
- "help": User wants help with available commands
- "unknown": Message doesn't match any intent

Message: "{text}"

Respond with ONLY the intent name (next, done, skip, tasks, morning, sync, help, or unknown)."""

        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )

        intent = response.choices[0].message.content.strip().lower()
        if intent in INTENT_HANDLERS:
            logger.info(f"AI classified '{text}' as intent: {intent}")
            return intent
        return None

    except Exception as e:
        logger.warning(f"AI intent classification failed: {e}")
        return None


async def route_message(text: str, user_id: str) -> Optional[dict]:
    """Route message to appropriate handler.

    Returns:
        dict with 'text' and optional 'blocks', or None if no match
    """
    text_lower = text.lower().strip()

    # Try regex patterns first (fast path)
    for pattern, handler in COMMAND_PATTERNS:
        if re.search(pattern, text_lower):
            return await handler(user_id)

    # Fall back to AI intent classification
    intent = await classify_intent_with_ai(text)
    if intent and intent in INTENT_HANDLERS:
        return await INTENT_HANDLERS[intent](user_id)

    return None


# =============================================================================
# Bot Runner
# =============================================================================


def create_app():
    """Create and configure the Slack Bolt app."""
    from slack_bolt.async_app import AsyncApp

    bolt_app = AsyncApp(token=settings.slack_bot_token)

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
                blocks=[slack_blocks.section("🤔 I didn't understand that. Here's what I can do:")] +
                       help_response.get("blocks", []),
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
