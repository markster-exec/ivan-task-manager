"""Import decisions from offline review.

Imports decisions from outbox/decisions.json after offline review.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from .models import Task

logger = logging.getLogger(__name__)


@dataclass
class ImportResult:
    """Result of an import operation."""

    success: bool
    message: str
    approved: int
    rejected: int
    edited: int


class OfflineImporter:
    """Import decisions from offline bundle."""

    def __init__(self, db_session: Session):
        """Initialize importer with database session.

        Args:
            db_session: SQLAlchemy session for updating tasks
        """
        self.db = db_session

    def import_decisions(self, bundle_path: Path) -> ImportResult:
        """Import decisions from outbox/decisions.json.

        Args:
            bundle_path: Path to the export bundle

        Returns:
            ImportResult with counts
        """
        decisions_file = bundle_path / "outbox" / "decisions.json"

        if not decisions_file.exists():
            return ImportResult(
                success=False,
                message="No decisions.json found in outbox/",
                approved=0,
                rejected=0,
                edited=0,
            )

        try:
            with open(decisions_file) as f:
                decisions = json.load(f)
        except json.JSONDecodeError as e:
            return ImportResult(
                success=False,
                message=f"Invalid JSON in decisions.json: {e}",
                approved=0,
                rejected=0,
                edited=0,
            )

        approved = 0
        rejected = 0
        edited = 0

        for decision in decisions:
            task_id = decision.get("task_id")
            decision_type = decision.get("decision")

            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.warning(f"Task {task_id} not found, skipping")
                continue

            if decision_type == "approve":
                # Keep task as-is, ready for posting
                approved += 1

            elif decision_type == "approve_edited":
                # Update action body with edited content
                if task.action and decision.get("edited_body"):
                    action = task.action.copy()
                    action["body"] = decision["edited_body"]
                    task.action = action
                    edited += 1

            elif decision_type == "reject":
                # Mark task as rejected/skipped
                task.status = "rejected"
                rejected += 1

        self.db.commit()

        return ImportResult(
            success=True,
            message=f"Imported {len(decisions)} decisions",
            approved=approved,
            rejected=rejected,
            edited=edited,
        )
