"""Pydantic models for entities (people/companies with context)."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class Workstream(BaseModel):
    """A project or initiative within an entity relationship."""

    id: str
    name: str
    status: Literal["planned", "active", "blocked", "complete"]
    deadline: Optional[date] = None
    milestone: Optional[str] = None
    revenue_potential: Optional[str] = None


class Entity(BaseModel):
    """A person or company Ivan has a relationship with."""

    # Required fields
    id: str
    type: Literal["person", "company"]
    name: str
    created: date
    updated: date
    tags: list[str] = []

    # Optional identity
    company: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    phone: Optional[str] = None

    # Relationship
    relationship_type: Optional[str] = None
    priority: Optional[int] = None
    intention: Optional[str] = None

    # Workstreams & channels
    workstreams: list[Workstream] = []
    channels: dict[str, str] = {}
    context_summary: Optional[str] = None

    # Relationship type to priority mapping
    _RELATIONSHIP_DEFAULTS = {
        "team": 5,
        "client": 4,
        "investor": 4,
        "prospect": 3,
        "partner": 3,
        "vendor": 1,
        "network": 1,
    }

    def get_priority(self) -> int:
        """Return priority, defaulting from relationship_type."""
        if self.priority is not None:
            return self.priority
        return self._RELATIONSHIP_DEFAULTS.get(self.relationship_type, 2)

    def get_active_workstream(self) -> Optional[Workstream]:
        """Return first active workstream, or None."""
        for ws in self.workstreams:
            if ws.status == "active":
                return ws
        return None

    def get_workstream(self, workstream_id: str) -> Optional[Workstream]:
        """Return workstream by ID, or None."""
        for ws in self.workstreams:
            if ws.id == workstream_id:
                return ws
        return None
