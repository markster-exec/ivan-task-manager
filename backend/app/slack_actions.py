"""Slack interactive component handlers.

Handles button clicks and modal submissions for task actions:
- Defer: Update due date
- Done: Mark complete with optional context
- Snooze: Hide locally
- Delegate: Reassign to team member
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from . import slack_blocks
from .models import Task, SessionLocal
from .writers import get_writer

logger = logging.getLogger(__name__)

# Team member ID mappings
TEAM_MEMBERS = {
    "attila": {
        "clickup_id": "81842673",
        "github_username": "atiti",
        "display_name": "Attila",
    },
    "tamas": {
        "clickup_id": "2695145",
        "github_username": None,  # Not a GitHub collaborator
        "display_name": "Tamas",
    },
}


def get_task_by_id(task_id: str) -> Optional[Task]:
    """Get task from database by ID."""
    db = SessionLocal()
    try:
        return db.query(Task).filter(Task.id == task_id).first()
    finally:
        db.close()


def register_action_handlers(bolt_app):
    """Register all action handlers on the Bolt app.

    Call this from bot.py after creating the app.
    """

    # =========================================================================
    # Defer Action
    # =========================================================================

    @bolt_app.action("defer_button")
    async def handle_defer_button(ack, body, client):
        """Open defer modal when button is clicked."""
        await ack()

        task_id = body["actions"][0]["value"]
        task = get_task_by_id(task_id)

        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=slack_blocks.defer_modal(task_id, task.title),
        )

    @bolt_app.view("defer_modal")
    async def handle_defer_submit(ack, body, client, view):
        """Process defer modal submission."""
        await ack()

        task_id = view["private_metadata"]
        days = int(
            view["state"]["values"]["defer_option"]["defer_select"]["selected_option"][
                "value"
            ]
        )

        new_date = (datetime.now() + timedelta(days=days)).date()

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return

            # Update source system
            source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
            writer = get_writer(task.source)
            result = await writer.update_due_date(source_id, new_date)

            if result.success:
                # Update local DB
                task.due_date = new_date
                task.escalation_level = 0  # Reset escalation
                task.last_notified_at = None
                db.commit()

                # Notify user
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=f"Deferred *{task.title}* to {new_date.isoformat()}",
                )
                logger.info(f"Deferred task {task_id} to {new_date}")
            else:
                await client.chat_postMessage(
                    channel=body["user"]["id"],
                    text=f"Failed to defer: {result.message}",
                )

        finally:
            db.close()

    # =========================================================================
    # Done Action
    # =========================================================================

    @bolt_app.action("done_button")
    async def handle_done_button(ack, body, client):
        """Open done modal when button is clicked."""
        await ack()

        task_id = body["actions"][0]["value"]
        task = get_task_by_id(task_id)

        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=slack_blocks.done_modal(task_id, task.title),
        )

    @bolt_app.view("done_modal")
    async def handle_done_submit(ack, body, client, view):
        """Process done modal submission."""
        await ack()

        task_id = view["private_metadata"]

        # Get optional context
        context_block = view["state"]["values"].get("done_context", {})
        context_input = context_block.get("context_input", {})
        context_text = context_input.get("value", "")

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return

            source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
            writer = get_writer(task.source)

            # Add comment with context if provided
            if context_text:
                await writer.comment(source_id, f"Completed: {context_text}")

            # Mark complete in source
            result = await writer.complete(source_id)

            if result.success:
                # Update local DB
                task.status = "done"
                task.updated_at = datetime.utcnow()
                db.commit()

                # Notify user
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=f"Completed *{task.title}*",
                )
                logger.info(f"Completed task {task_id}")
            else:
                await client.chat_postMessage(
                    channel=body["user"]["id"],
                    text=f"Failed to complete: {result.message}",
                )

        finally:
            db.close()

    # =========================================================================
    # Snooze Action
    # =========================================================================

    @bolt_app.action("snooze_button")
    async def handle_snooze_button(ack, body, client):
        """Open snooze modal when button is clicked."""
        await ack()

        task_id = body["actions"][0]["value"]
        task = get_task_by_id(task_id)

        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=slack_blocks.snooze_modal(task_id, task.title),
        )

    @bolt_app.view("snooze_modal")
    async def handle_snooze_submit(ack, body, client, view):
        """Process snooze modal submission."""
        await ack()

        task_id = view["private_metadata"]
        days = int(
            view["state"]["values"]["snooze_option"]["snooze_select"][
                "selected_option"
            ]["value"]
        )

        snooze_until = datetime.utcnow() + timedelta(days=days)

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return

            # Snooze is LOCAL ONLY - no source system update
            task.snooze_until = snooze_until
            db.commit()

            # Notify user
            user_id = body["user"]["id"]
            await client.chat_postMessage(
                channel=user_id,
                text=f"Snoozed *{task.title}* until {snooze_until.strftime('%Y-%m-%d')}",
            )
            logger.info(f"Snoozed task {task_id} until {snooze_until}")

        finally:
            db.close()

    # =========================================================================
    # Delegate Action
    # =========================================================================

    @bolt_app.action("delegate_button")
    async def handle_delegate_button(ack, body, client):
        """Open delegate modal when button is clicked."""
        await ack()

        task_id = body["actions"][0]["value"]
        task = get_task_by_id(task_id)

        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        await client.views_open(
            trigger_id=body["trigger_id"],
            view=slack_blocks.delegate_modal(task_id, task.title),
        )

    @bolt_app.view("delegate_modal")
    async def handle_delegate_submit(ack, body, client, view):
        """Process delegate modal submission."""
        await ack()

        task_id = view["private_metadata"]
        person_key = view["state"]["values"]["delegate_option"]["delegate_select"][
            "selected_option"
        ]["value"]

        person = TEAM_MEMBERS.get(person_key)
        if not person:
            logger.error(f"Unknown team member: {person_key}")
            return

        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"Task not found: {task_id}")
                return

            source_id = task.id.split(":", 1)[1] if ":" in task.id else task.id
            writer = get_writer(task.source)

            # Get the appropriate ID for the source system
            if task.source == "clickup":
                assignee_id = person["clickup_id"]
            elif task.source == "github":
                assignee_id = person["github_username"]
                if not assignee_id:
                    await client.chat_postMessage(
                        channel=body["user"]["id"],
                        text=f"{person['display_name']} is not a GitHub collaborator. Task not reassigned.",
                    )
                    return
            else:
                logger.error(f"Unknown source: {task.source}")
                return

            result = await writer.reassign(source_id, assignee_id)

            if result.success:
                # Update local DB
                task.assignee = person_key
                db.commit()

                # Notify user
                user_id = body["user"]["id"]
                await client.chat_postMessage(
                    channel=user_id,
                    text=f"Delegated *{task.title}* to {person['display_name']}",
                )
                logger.info(f"Delegated task {task_id} to {person_key}")
            else:
                await client.chat_postMessage(
                    channel=body["user"]["id"],
                    text=f"Failed to delegate: {result.message}",
                )

        finally:
            db.close()
