"""Natural language intent parser.

Extracts structured intents and parameters from user messages.
Uses regex for fast matching, falls back to AI for complex queries.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from .ai_engine import AIEngine, get_ai_engine

logger = logging.getLogger(__name__)


@dataclass
class ParsedIntent:
    """Structured intent extracted from user message."""

    intent: str  # next, done, skip, tasks, defer, entity_query, research, help, unknown
    params: dict = field(default_factory=dict)
    confidence: float = 1.0
    raw_text: str = ""


# Regex patterns for fast matching (high confidence)
REGEX_PATTERNS = [
    # Core commands
    (r"^\s*(next|what('?s| should i (work on|do)))\s*$", "next", {}),
    (r"^\s*(done|finished|completed|i finished)\s*$", "done", {}),
    (r"^\s*(skip|later|not now)\s*$", "skip", {}),
    (r"^\s*(tasks|show( my)? tasks|list|todo)\s*$", "tasks", {}),
    (r"^\s*(morning|briefing|brief me)\s*$", "morning", {}),
    (r"^\s*(sync|refresh|update)\s*$", "sync", {}),
    (r"^\s*(projects|workstreams)\s*$", "projects", {}),
    (r"^\s*(help|commands|\?)\s*$", "help", {}),
    # Entity query patterns
    (
        r"(?:what'?s happening with|status of|show me|tell me about)\s+(\w+)",
        "entity_query",
        lambda m: {"entity_name": m.group(1)},
    ),
    # Research patterns
    (
        r"(?:find|search|look up|research)\s+(.+)",
        "research",
        lambda m: {"query": m.group(1)},
    ),
]

# Date word to days mapping
DATE_WORDS = {
    "tomorrow": 1,
    "monday": None,  # Calculate from today
    "tuesday": None,
    "wednesday": None,
    "thursday": None,
    "friday": None,
    "saturday": None,
    "sunday": None,
    "next week": 7,
    "next monday": None,
}


def _parse_date_to_days(text: str) -> Optional[int]:
    """Parse date reference to number of days from now."""
    text_lower = text.lower().strip()

    # Direct day counts
    if match := re.search(r"(\d+)\s*days?", text_lower):
        return int(match.group(1))
    if match := re.search(r"(\d+)\s*weeks?", text_lower):
        return int(match.group(1)) * 7

    # Named references
    if "tomorrow" in text_lower:
        return 1
    if "next week" in text_lower:
        return 7
    if "monday" in text_lower:
        # Calculate days until next Monday
        from datetime import datetime

        today = datetime.now().weekday()  # 0 = Monday
        days_until_monday = (7 - today) % 7
        if days_until_monday == 0:
            days_until_monday = 7  # Next Monday, not today
        return days_until_monday

    return None


class IntentParser:
    """Parse natural language into structured intents."""

    def __init__(self, ai_engine: Optional[AIEngine] = None):
        """Initialize parser.

        Args:
            ai_engine: AI engine for complex parsing (uses singleton if None)
        """
        self.ai = ai_engine or get_ai_engine()

    def _try_regex(self, text: str) -> Optional[ParsedIntent]:
        """Try regex patterns for fast matching."""
        text_lower = text.lower().strip()

        for pattern, intent, param_extractor in REGEX_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                if callable(param_extractor):
                    params = param_extractor(match)
                else:
                    params = param_extractor.copy() if param_extractor else {}

                return ParsedIntent(
                    intent=intent,
                    params=params,
                    confidence=1.0,
                    raw_text=text,
                )

        return None

    async def parse(self, text: str) -> ParsedIntent:
        """Parse user message into intent + parameters.

        Args:
            text: Raw user message

        Returns:
            ParsedIntent with extracted intent and parameters
        """
        # Try regex first (fast path)
        result = self._try_regex(text)
        if result:
            logger.debug(f"Regex matched intent: {result.intent}")
            return result

        # Fall back to AI for complex queries
        result = await self._parse_with_ai(text)
        if result and result.intent != "unknown":
            logger.info(
                f"AI parsed intent: {result.intent} (conf: {result.confidence})"
            )
            return result

        # AI failed or returned unknown
        return ParsedIntent(
            intent="unknown",
            params={},
            confidence=0.0,
            raw_text=text,
        )

    async def _parse_with_ai(self, text: str) -> Optional[ParsedIntent]:
        """Parse intent using AI."""
        prompt = f"""Analyze this message and extract the intent and parameters.

Intents:
- "next": User wants their next task to work on
- "done": User completed their current task
- "skip": User wants to skip/defer current task
- "tasks": User wants to see all their tasks
- "morning": User wants morning briefing
- "sync": User wants to sync/refresh tasks
- "defer": User wants to postpone task(s) to a later date
- "entity_query": User asking about a person or company
- "research": User wants information searched on the web
- "help": User wants help with commands
- "unknown": Doesn't match any intent

For "defer", extract:
- entity: person/company name if mentioned (or null)
- days: number of days to defer (e.g., "monday" = days until monday, "next week" = 7)

For "entity_query", extract:
- entity_name: the person or company name

For "research", extract:
- query: what to search for

Message: "{text}"

Respond with JSON:
{{"intent": "...", "params": {{}}, "confidence": 0.0-1.0}}"""

        result = await self.ai.complete_json(prompt, max_tokens=200)

        if not result:
            return None

        intent = result.get("intent", "unknown")
        params = result.get("params", {})
        confidence = result.get("confidence", 0.5)

        # Post-process date params
        if intent == "defer" and "date" in params:
            days = _parse_date_to_days(str(params["date"]))
            if days:
                params["days"] = days

        return ParsedIntent(
            intent=intent,
            params=params,
            confidence=float(confidence),
            raw_text=text,
        )


# Singleton instance
_parser: Optional[IntentParser] = None


def get_intent_parser() -> IntentParser:
    """Get or create the intent parser singleton."""
    global _parser
    if _parser is None:
        _parser = IntentParser()
    return _parser
