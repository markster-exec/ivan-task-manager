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

settings = get_settings()
logger = logging.getLogger(__name__)


# =============================================================================
# Command Handlers
# =============================================================================


async def handle_next(user_id: str) -> str:
    """Get the next highest priority task."""
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return "✅ No tasks in queue! Enjoy your free time."

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
        if len(desc) > 200:
            desc = desc[:200] + "..."

        return f"""🎯 *Focus on this:*

*{task.title}*
Score: {task.score} | {' | '.join(flags)}

{desc}

🔗 {task.url}

_Reply "done" when finished, "skip" to move to next._"""

    finally:
        db.close()


async def handle_done(user_id: str) -> str:
    """Mark current task as done."""
    db = SessionLocal()
    try:
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

        if not current or not current.task_id:
            return '❓ No current task. Say "next" to get one.'

        task = db.query(Task).filter(Task.id == current.task_id).first()
        if not task:
            return '❓ Current task not found. Say "next" to get a new one.'

        # Mark as done
        task.status = "done"
        completed_title = task.title
        db.commit()

        # Get next task
        return f"✅ Completed: *{completed_title}*\n\n" + await handle_next(user_id)

    finally:
        db.close()


async def handle_skip(user_id: str) -> str:
    """Skip current task and get next one."""
    db = SessionLocal()
    try:
        current = db.query(CurrentTask).filter(CurrentTask.user_id == "ivan").first()

        if not current or not current.task_id:
            return '❓ No current task to skip. Say "next" to get one.'

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
            return f"⏭️ Skipped: *{skipped_title}*\n\nNo more tasks in queue."

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

        return f"""⏭️ Skipped: *{skipped_title}*

🎯 *Next up:*

*{next_task.title}*
Score: {next_task.score} | {' | '.join(flags)}

🔗 {next_task.url}"""

    finally:
        db.close()


async def handle_tasks(user_id: str) -> str:
    """Show all tasks sorted by priority."""
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return "✅ No tasks in queue!"

        tasks = score_and_sort_tasks(tasks)

        lines = ["📋 *Your Tasks* (sorted by priority)\n"]
        for i, task in enumerate(tasks[:10], 1):
            breakdown = get_score_breakdown(task)
            emoji = "🔴" if task.score >= 1000 else "🟡" if task.score >= 500 else "🟢"
            lines.append(
                f"{emoji} {i}. *{task.title}*\n"
                f"    Score: {task.score} | {breakdown['urgency_label']}\n"
                f"    🔗 {task.url}"
            )

        if len(tasks) > 10:
            lines.append(f"\n_...and {len(tasks) - 10} more tasks_")

        lines.append(f"\n*Total: {len(tasks)} tasks*")
        return "\n".join(lines)

    finally:
        db.close()


async def handle_morning(user_id: str) -> str:
    """Get morning briefing."""
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task).filter(Task.status != "done", Task.assignee == "ivan").all()
        )

        if not tasks:
            return "☀️ *Good morning!*\n\nNo tasks in queue. Enjoy your day!"

        tasks = score_and_sort_tasks(tasks)

        # Top 3
        top_3 = tasks[:3]
        focus_lines = []
        for i, task in enumerate(top_3, 1):
            breakdown = get_score_breakdown(task)
            flags = []
            if task.is_revenue:
                flags.append("Revenue")
            if task.is_blocking:
                flags.append(f"Blocking: {', '.join(task.is_blocking)}")
            flags.append(breakdown["urgency_label"])

            focus_lines.append(
                f"{i}. *{task.title}* (Score: {task.score})\n"
                f"   → {' | '.join(flags)}\n"
                f"   🔗 {task.url}"
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

        return f"""☀️ *Good morning, Ivan!*

🔥 *TOP 3 FOCUS*
{chr(10).join(focus_lines)}

📊 *SUMMARY*
• {len(tasks)} total tasks
• {overdue} overdue
• {due_today} due today
• {len(blocking)} people waiting on you

Say "next" to start working!"""

    finally:
        db.close()


async def handle_sync(user_id: str) -> str:
    """Force sync from all sources."""
    try:
        results = await sync_all_sources()
        return f"""🔄 *Sync complete!*

• ClickUp: {results.get('clickup', 0)} tasks
• GitHub: {results.get('github', 0)} tasks

Say "tasks" to see updated list."""
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return f"❌ Sync failed: {str(e)}"


async def handle_help(user_id: str) -> str:
    """Show available commands."""
    return """👋 *Ivan Task Manager*

*Commands:*
• *next* - Get your highest priority task
• *done* - Mark current task complete
• *skip* - Skip to next task
• *tasks* - Show all your tasks
• *morning* - Get morning briefing
• *sync* - Refresh from ClickUp/GitHub
• *help* - Show this message

You can also ask naturally:
• "What should I work on?"
• "I finished the task"
• "Show me my tasks"
"""


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


async def route_message(text: str, user_id: str) -> Optional[str]:
    """Route message to appropriate handler."""
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

        logger.info(f"Received DM from {user_id}: {text}")

        response = await route_message(text, user_id)

        if response:
            await say(response)
        else:
            # Unknown command - show help
            await say(
                "🤔 I didn't understand that. Here's what I can do:\n\n"
                + await handle_help(user_id)
            )

    @bolt_app.event("app_mention")
    async def handle_app_mention(event: dict, say):
        """Handle @mentions in channels."""
        text = event.get("text", "")
        user_id = event.get("user", "")

        # Remove the mention itself
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        logger.info(f"Mentioned by {user_id}: {text}")

        response = await route_message(text, user_id)

        if response:
            await say(response)
        else:
            await say('👋 DM me for task management! Say "help" to see commands.')

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
