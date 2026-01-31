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


def format_completion(
    completed_title: str, url: Optional[str] = None
) -> tuple[str, list[dict]]:
    """Format task completion confirmation.

    Args:
        completed_title: Title of the completed task
        url: Optional URL to the task in source system

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"✅ Completed: {completed_title}"
    if url:
        blocks = [section(f"✅ *Completed:* <{url}|{completed_title}>")]
    else:
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


def action_buttons(task_id: str) -> dict:
    """Create interactive action buttons for escalation messages.

    Args:
        task_id: Task ID for button action values
    """
    return {
        "type": "actions",
        "block_id": f"task_actions_{task_id}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Defer", "emoji": True},
                "value": task_id,
                "action_id": "defer_button",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Done", "emoji": True},
                "value": task_id,
                "action_id": "done_button",
                "style": "primary",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Snooze", "emoji": True},
                "value": task_id,
                "action_id": "snooze_button",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Delegate", "emoji": True},
                "value": task_id,
                "action_id": "delegate_button",
            },
        ],
    }


# Keep placeholder for backwards compatibility during transition
action_buttons_placeholder = action_buttons


def defer_modal(task_id: str, task_title: str) -> dict:
    """Create modal for defer action with date options."""
    return {
        "type": "modal",
        "callback_id": "defer_modal",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Defer Task"},
        "submit": {"type": "plain_text", "text": "Defer"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            section(f"*{task_title}*"),
            {
                "type": "input",
                "block_id": "defer_option",
                "element": {
                    "type": "static_select",
                    "action_id": "defer_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select new due date",
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Tomorrow"},
                            "value": "1",
                        },
                        {
                            "text": {"type": "plain_text", "text": "3 days"},
                            "value": "3",
                        },
                        {
                            "text": {"type": "plain_text", "text": "1 week"},
                            "value": "7",
                        },
                        {
                            "text": {"type": "plain_text", "text": "2 weeks"},
                            "value": "14",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "Defer until"},
            },
        ],
    }


def done_modal(task_id: str, task_title: str) -> dict:
    """Create modal for done action with optional context."""
    return {
        "type": "modal",
        "callback_id": "done_modal",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Complete Task"},
        "submit": {"type": "plain_text", "text": "Mark Done"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            section(f"*{task_title}*"),
            {
                "type": "input",
                "block_id": "done_context",
                "optional": True,
                "element": {
                    "type": "plain_text_input",
                    "action_id": "context_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "What happened? (optional)",
                    },
                    "max_length": 500,
                },
                "label": {"type": "plain_text", "text": "Context"},
            },
        ],
    }


def snooze_modal(task_id: str, task_title: str) -> dict:
    """Create modal for snooze action."""
    return {
        "type": "modal",
        "callback_id": "snooze_modal",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Snooze Task"},
        "submit": {"type": "plain_text", "text": "Snooze"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            section(f"*{task_title}*"),
            context(
                "Snoozing hides the task locally without changing the source system."
            ),
            {
                "type": "input",
                "block_id": "snooze_option",
                "element": {
                    "type": "static_select",
                    "action_id": "snooze_select",
                    "placeholder": {"type": "plain_text", "text": "Snooze for..."},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "1 day"},
                            "value": "1",
                        },
                        {
                            "text": {"type": "plain_text", "text": "3 days"},
                            "value": "3",
                        },
                        {
                            "text": {"type": "plain_text", "text": "1 week"},
                            "value": "7",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "Snooze duration"},
            },
        ],
    }


def delegate_modal(task_id: str, task_title: str) -> dict:
    """Create modal for delegate action."""
    return {
        "type": "modal",
        "callback_id": "delegate_modal",
        "private_metadata": task_id,
        "title": {"type": "plain_text", "text": "Delegate Task"},
        "submit": {"type": "plain_text", "text": "Delegate"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            section(f"*{task_title}*"),
            {
                "type": "input",
                "block_id": "delegate_option",
                "element": {
                    "type": "static_select",
                    "action_id": "delegate_select",
                    "placeholder": {"type": "plain_text", "text": "Select person"},
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": "Attila"},
                            "value": "attila",
                        },
                        {
                            "text": {"type": "plain_text", "text": "Tamas"},
                            "value": "tamas",
                        },
                    ],
                },
                "label": {"type": "plain_text", "text": "Delegate to"},
            },
        ],
    }


def format_escalation_message(
    title: str,
    url: str,
    due_date: str,
    escalation_level: int,
    task_id: str,
) -> tuple[str, list[dict]]:
    """Format an escalation notification with action buttons.

    Args:
        title: Task title
        url: Task URL
        due_date: Due date string
        escalation_level: Level (3, 5, or 7)
        task_id: Task ID for button actions

    Returns:
        Tuple of (text fallback, blocks)
    """
    # Emoji and message based on level
    if escalation_level >= 7:
        emoji = "⚫"
        level_msg = "7+ days overdue"
        extra = "\n_Removing from active list unless you respond_"
    elif escalation_level >= 5:
        emoji = "🔴"
        level_msg = "5 days overdue"
        extra = "\n_Should I delegate or kill it?_"
    else:
        emoji = "🟠"
        level_msg = "3 days overdue"
        extra = ""

    text = f"{emoji} {level_msg}: {title}"

    blocks = [
        section(f"{emoji} *{level_msg}*\n<{url}|{title}>\nWas due: {due_date}{extra}"),
        action_buttons_placeholder(task_id),
    ]

    return text, blocks


def format_grouped_escalation(
    tasks_data: list[dict],
    escalation_level: int,
) -> tuple[str, list[dict]]:
    """Format a grouped escalation message for 3+ tasks.

    Args:
        tasks_data: List of dicts with title, url, due_date, task_id
        escalation_level: Shared escalation level

    Returns:
        Tuple of (text fallback, blocks)
    """
    count = len(tasks_data)

    if escalation_level >= 7:
        emoji = "⚫"
        level_msg = "7+ days overdue"
    elif escalation_level >= 5:
        emoji = "🔴"
        level_msg = "5 days overdue"
    else:
        emoji = "🟠"
        level_msg = "3 days overdue"

    text = f"{emoji} {count} tasks are {level_msg}"

    blocks = [
        section(f"{emoji} *{count} tasks are {level_msg}*"),
        divider(),
    ]

    # List each task
    for i, task in enumerate(tasks_data[:10], 1):
        blocks.append(
            section(
                f"*{i}.* <{task['url']}|{task['title']}>\n"
                f"      Due: {task['due_date']}"
            )
        )

    if count > 10:
        blocks.append(context(f"_...and {count - 10} more_"))

    # Add suggestion
    blocks.append(divider())
    blocks.append(section("_Want me to bulk-defer these to next week?_"))

    return text, blocks


def format_briefing_with_buttons(
    greeting: str,
    location: Optional[str],
    top_tasks: list[dict],
    stats: dict,
    calendar_events: list[dict],
    suggestion: Optional[str],
) -> tuple[str, list[dict]]:
    """Format morning briefing with enhanced layout.

    Args:
        greeting: Greeting string (Good morning, etc.)
        location: Optional location string
        top_tasks: List of dicts with title, url, score, flags, task_id
        stats: Dict with total, overdue, due_today, blocking_people
        calendar_events: List of calendar event dicts
        suggestion: Optional suggestion text

    Returns:
        Tuple of (text fallback, blocks)
    """
    text = f"☀️ {greeting}! {stats['total']} tasks, {stats['overdue']} overdue"

    # Header
    location_line = f"\n📍 You're in {location}" if location else ""
    blocks = [
        section(f"☀️ *{greeting}, Ivan*{location_line}"),
        divider(),
        section("🔥 *TOP 3 FOCUS*"),
    ]

    # Top tasks with inline buttons
    for i, task in enumerate(top_tasks[:3], 1):
        flags_str = " | ".join(task["flags"]) if task.get("flags") else ""
        blocks.append(
            section(
                f"*{i}.* <{task['url']}|{task['title']}> (Score: {task['score']})\n"
                f"      → {flags_str}"
            )
        )

    # Stats
    blocking_str = (
        ", ".join(stats["blocking_people"]) if stats["blocking_people"] else "none"
    )
    blocks.extend(
        [
            divider(),
            section(
                f"📊 *SUMMARY*\n"
                f"• {stats['total']} tasks total, {stats['overdue']} overdue\n"
                f"• {stats['due_today']} due today\n"
                f"• {len(stats['blocking_people'])} people waiting on you ({blocking_str})"
            ),
        ]
    )

    # Calendar
    blocks.append(divider())
    if calendar_events:
        cal_lines = []
        for event in calendar_events[:3]:
            cal_lines.append(f"• {event['time']} - {event['title']}")
        blocks.append(section("📅 *TODAY*\n" + "\n".join(cal_lines)))
    else:
        blocks.append(section("📅 *TODAY*\n_No events scheduled_"))

    # Suggestion
    if suggestion:
        blocks.extend(
            [
                divider(),
                section(f"💡 *SUGGESTION*\n{suggestion}"),
            ]
        )

    blocks.append(context("Type `ivan next` to start working."))

    return text, blocks
