"""Slack Block Kit message formatting utilities.

Provides functions to create rich, structured Slack messages.
"""

from typing import Optional


def section(text: str) -> dict:
    """Create a section block with mrkdwn text."""
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": text},
    }


def divider() -> dict:
    """Create a divider block."""
    return {"type": "divider"}


def context(text: str) -> dict:
    """Create a context block with mrkdwn text."""
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text}],
    }


def header(text: str) -> dict:
    """Create a header block."""
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": text, "emoji": True},
    }


def format_task_block(
    title: str,
    url: str,
    score: int,
    flags: list[str],
    description: Optional[str] = None,
) -> list[dict]:
    """Format a task as Block Kit blocks.

    Args:
        title: Task title
        url: Task URL
        score: Task priority score
        flags: List of flag strings (Revenue, Blocking, urgency)
        description: Optional task description

    Returns:
        List of Block Kit blocks
    """
    blocks = [
        section(f"*<{url}|{title}>*"),
        context(f"Score: {score} | {' | '.join(flags)}"),
    ]

    if description:
        desc = description[:300] + "..." if len(description) > 300 else description
        blocks.append(section(f"_{desc}_"))

    return blocks


def format_task_list_item(
    index: int,
    title: str,
    url: str,
    score: int,
    urgency_label: str,
    emoji: str = "🟢",
) -> str:
    """Format a single task list item as mrkdwn text.

    Args:
        index: Position in list (1-based)
        title: Task title
        url: Task URL
        score: Task priority score
        urgency_label: Urgency description
        emoji: Priority emoji (🔴, 🟡, 🟢)

    Returns:
        Formatted mrkdwn string
    """
    return f"{emoji} *{index}.* <{url}|{title}>\n      Score: {score} | {urgency_label}"


def format_next_task(
    title: str,
    url: str,
    score: int,
    flags: list[str],
    description: str,
) -> tuple[str, list[dict]]:
    """Format the 'next task' response with Block Kit.

    Returns:
        Tuple of (text fallback, blocks)
    """
    desc = description[:200] + "..." if len(description) > 200 else description

    text = f"🎯 Focus on: {title} (Score: {score})"

    blocks = [
        section("🎯 *Focus on this:*"),
        divider(),
        section(f"*<{url}|{title}>*"),
        context(f"Score: {score} | {' | '.join(flags)}"),
        section(f"_{desc}_"),
        divider(),
        context('_Reply "done" when finished, "skip" to move to next._'),
    ]

    return text, blocks


def format_task_list(
    tasks_data: list[dict], total_count: int
) -> tuple[str, list[dict]]:
    """Format the task list response with Block Kit.

    Args:
        tasks_data: List of dicts with title, url, score, urgency_label, emoji
        total_count: Total number of tasks

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"📋 Your Tasks - {total_count} total"

    blocks = [
        section(f"📋 *Your Tasks* ({total_count} total)"),
        divider(),
    ]

    for i, task in enumerate(tasks_data[:10], 1):
        item = format_task_list_item(
            index=i,
            title=task["title"],
            url=task["url"],
            score=task["score"],
            urgency_label=task["urgency_label"],
            emoji=task["emoji"],
        )
        blocks.append(section(item))

    if total_count > 10:
        blocks.append(context(f"_...and {total_count - 10} more tasks_"))

    return text, blocks


def format_morning_briefing(
    focus_tasks: list[dict],
    stats: dict,
) -> tuple[str, list[dict]]:
    """Format the morning briefing with Block Kit.

    Args:
        focus_tasks: List of dicts with title, url, score, flags
        stats: Dict with total, overdue, due_today, blocking_count

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"☀️ Good morning! {stats['total']} tasks, {stats['overdue']} overdue"

    blocks = [
        section("☀️ *Good morning, Ivan!*"),
        divider(),
        section("🔥 *TOP 3 FOCUS*"),
    ]

    for i, task in enumerate(focus_tasks[:3], 1):
        blocks.append(
            section(
                f"*{i}.* <{task['url']}|{task['title']}>\n"
                f"      Score: {task['score']} | {' | '.join(task['flags'])}"
            )
        )

    blocks.extend(
        [
            divider(),
            section(
                f"📊 *SUMMARY*\n"
                f"• {stats['total']} total tasks\n"
                f"• {stats['overdue']} overdue\n"
                f"• {stats['due_today']} due today\n"
                f"• {stats['blocking_count']} people waiting on you"
            ),
            divider(),
            context('Say "next" to start working!'),
        ]
    )

    return text, blocks


def format_completion(completed_title: str) -> tuple[str, list[dict]]:
    """Format task completion confirmation.

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"✅ Completed: {completed_title}"
    blocks = [section(f"✅ *Completed:* {completed_title}")]
    return text, blocks


def format_skip(skipped_title: str) -> tuple[str, list[dict]]:
    """Format task skip confirmation.

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"⏭️ Skipped: {skipped_title}"
    blocks = [section(f"⏭️ *Skipped:* {skipped_title}")]
    return text, blocks
