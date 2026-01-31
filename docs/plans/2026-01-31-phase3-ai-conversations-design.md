---
id: phase3-ai-conversations-design
title: Phase 3 - AI Conversations Design
type: plan
status: active
owner: ivan
created: 2026-01-31
updated: 2026-01-31
tags: [slack-bot, phase-3, ai, nlp]
---

# Phase 3: AI Conversations Design

## Overview

Replace regex-based command matching with AI-powered intent parsing. Enable natural language task management, entity queries, and basic research.

## Deliverables

1. **AI engine** — Azure OpenAI wrapper with timeout and regex fallback
2. **Intent parser** — Extract intent + parameters from natural language
3. **Entity queries** — "What's happening with Kyle?"
4. **Research** — DuckDuckGo search + AI summarization

## Architecture

### New Files

| File | Purpose |
|------|---------|
| `backend/app/ai_engine.py` | Azure OpenAI wrapper with error handling |
| `backend/app/intent_parser.py` | Parse NL → structured intent + params |
| `backend/app/researcher.py` | Web search + summarize |

### Modified Files

| File | Change |
|------|--------|
| `backend/app/bot.py` | Use intent_parser instead of regex patterns |

## Intent Types

| Intent | Example | Parameters | Handler |
|--------|---------|------------|---------|
| `next` | "what should I work on?" | — | `handle_next` |
| `done` | "finished the proposal" | context? | `handle_done` |
| `skip` | "skip this one" | — | `handle_skip` |
| `tasks` | "show my tasks" | filter? | `handle_tasks` |
| `defer` | "defer Kyle stuff to Monday" | entity?, days | `handle_defer_nl` |
| `entity_query` | "what's happening with Kyle?" | entity_name | `handle_entity` |
| `research` | "find coworking spaces in LA" | query | `handle_research` |
| `help` | "what can you do?" | — | `handle_help` |
| `unknown` | (fallback) | — | show help |

## AI Engine (ai_engine.py)

```python
class AIEngine:
    """Azure OpenAI wrapper with timeout and error handling."""

    def __init__(self):
        self.client = AzureOpenAI(...)
        self.timeout = 10  # seconds

    async def complete(self, prompt: str, max_tokens: int = 500) -> str | None:
        """Get completion with timeout. Returns None on failure."""
        try:
            response = await asyncio.wait_for(
                self._call_api(prompt, max_tokens),
                timeout=self.timeout
            )
            return response
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"AI call failed: {e}")
            return None

    async def complete_json(self, prompt: str) -> dict | None:
        """Get JSON completion. Returns None on failure or invalid JSON."""
        ...
```

## Intent Parser (intent_parser.py)

```python
@dataclass
class ParsedIntent:
    intent: str  # next, done, defer, entity_query, research, etc.
    params: dict  # {entity: "kyle", days: 7, query: "..."}
    confidence: float  # 0.0-1.0
    raw_text: str

class IntentParser:
    """Parse natural language into structured intents."""

    def __init__(self, ai_engine: AIEngine):
        self.ai = ai_engine

    async def parse(self, text: str) -> ParsedIntent:
        """Parse user message into intent + parameters."""

        # Try regex first (fast path for exact matches)
        intent = self._try_regex(text)
        if intent:
            return intent

        # Fall back to AI
        prompt = self._build_parse_prompt(text)
        result = await self.ai.complete_json(prompt)

        if result:
            return ParsedIntent(
                intent=result.get("intent", "unknown"),
                params=result.get("params", {}),
                confidence=result.get("confidence", 0.5),
                raw_text=text
            )

        # AI failed, return unknown
        return ParsedIntent(
            intent="unknown",
            params={},
            confidence=0.0,
            raw_text=text
        )
```

### Parse Prompt

```
Analyze this message and extract the intent and parameters.

Intents:
- next: User wants their next task
- done: User completed a task (params: context)
- skip: User wants to skip current task
- tasks: User wants to see tasks (params: filter)
- defer: User wants to defer task(s) (params: entity, days)
- entity_query: User asking about a person/company (params: entity_name)
- research: User wants information searched (params: query)
- help: User wants help

Message: "{text}"

Respond with JSON only:
{"intent": "...", "params": {...}, "confidence": 0.0-1.0}
```

## Researcher (researcher.py)

```python
class Researcher:
    """Web search and summarization."""

    def __init__(self, ai_engine: AIEngine):
        self.ai = ai_engine

    async def search(self, query: str, num_results: int = 5) -> list[dict]:
        """Search DuckDuckGo and return results."""
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
        return results

    async def research(self, query: str) -> str:
        """Search and summarize results."""
        results = await self.search(query)

        if not results:
            return f"No results found for: {query}"

        # Format results for AI
        context = "\n".join([
            f"- {r['title']}: {r['body']}"
            for r in results[:5]
        ])

        prompt = f"""Based on these search results, provide a helpful summary.

Query: {query}

Results:
{context}

Provide a concise, actionable summary (2-3 sentences)."""

        summary = await self.ai.complete(prompt, max_tokens=200)
        return summary or f"Found {len(results)} results but couldn't summarize."
```

## Bot Integration

Replace `route_message()` in bot.py:

```python
# Initialize once
ai_engine = AIEngine()
intent_parser = IntentParser(ai_engine)
researcher = Researcher(ai_engine)

async def route_message(text: str, user_id: str) -> dict | None:
    """Route message using AI-powered intent parsing."""

    # Parse intent
    parsed = await intent_parser.parse(text)

    # Route to handler
    if parsed.intent == "next":
        return await handle_next(user_id)
    elif parsed.intent == "done":
        return await handle_done(user_id)
    elif parsed.intent == "skip":
        return await handle_skip(user_id)
    elif parsed.intent == "tasks":
        return await handle_tasks(user_id)
    elif parsed.intent == "defer":
        return await handle_defer_nl(user_id, parsed.params)
    elif parsed.intent == "entity_query":
        return await handle_entity(user_id, parsed.params.get("entity_name", ""))
    elif parsed.intent == "research":
        return await handle_research(user_id, parsed.params.get("query", text))
    elif parsed.intent == "help":
        return await handle_help(user_id)
    else:
        return None  # Will show help
```

## New Handlers

### handle_defer_nl

```python
async def handle_defer_nl(user_id: str, params: dict) -> dict:
    """Handle natural language defer command."""
    entity_name = params.get("entity")
    days = params.get("days", 7)

    db = SessionLocal()
    try:
        query = db.query(Task).filter(
            Task.status != "done",
            Task.assignee == "ivan"
        )

        # Filter by entity if specified
        if entity_name:
            # Find tasks matching entity
            entity = find_entity_by_name(entity_name)
            if entity:
                # Filter tasks by entity (check title, tags, etc.)
                ...

        # Calculate new due date
        new_date = (datetime.now() + timedelta(days=days)).date()

        # Defer matching tasks
        count = 0
        for task in matching_tasks:
            source_id = task.id.split(":", 1)[1]
            writer = get_writer(task.source)
            await writer.update_due_date(source_id, new_date)
            task.due_date = new_date
            count += 1

        db.commit()
        return {"text": f"Deferred {count} tasks to {new_date}"}
    finally:
        db.close()
```

### handle_research

```python
async def handle_research(user_id: str, query: str) -> dict:
    """Handle research query."""
    summary = await researcher.research(query)

    return {
        "text": summary,
        "blocks": [
            slack_blocks.section(f"🔍 *Research: {query}*"),
            slack_blocks.divider(),
            slack_blocks.section(summary),
        ]
    }
```

## Dependencies

Add to requirements.txt:
```
duckduckgo-search>=4.0
```

## Testing Strategy

1. **Unit tests** for IntentParser (mock AI responses)
2. **Unit tests** for Researcher (mock DuckDuckGo)
3. **Integration tests** for full flow (mock external APIs)

## Success Criteria

- [ ] "defer X to Monday" works via natural language
- [ ] "what's happening with Kyle" returns entity summary
- [ ] Research queries return useful summaries
- [ ] Graceful fallback when AI fails (regex still works)
- [ ] Response time < 3 seconds for most queries

## Implementation Order

1. Create `ai_engine.py` — Azure OpenAI wrapper
2. Create `intent_parser.py` — NL parsing
3. Create `researcher.py` — Web search + summarize
4. Update `bot.py` — Integrate new routing
5. Add new handlers — `handle_defer_nl`, `handle_research`
6. Write tests
7. Manual testing in Slack
