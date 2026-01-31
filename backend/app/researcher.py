"""Web search and summarization for research queries.

Uses DuckDuckGo for search (no API key required) and AI for summarization.
"""

import asyncio
import logging
from typing import Optional

from .ai_engine import AIEngine, get_ai_engine

logger = logging.getLogger(__name__)


class Researcher:
    """Web search and summarization."""

    def __init__(self, ai_engine: Optional[AIEngine] = None):
        """Initialize researcher.

        Args:
            ai_engine: AI engine for summarization (uses singleton if None)
        """
        self.ai = ai_engine or get_ai_engine()

    async def search(self, query: str, num_results: int = 5) -> list[dict]:
        """Search DuckDuckGo and return results.

        Args:
            query: Search query
            num_results: Maximum results to return

        Returns:
            List of result dicts with title, body, href
        """
        try:
            from duckduckgo_search import DDGS

            # Run sync search in thread pool
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=num_results)),
            )

            logger.info(f"Search '{query}' returned {len(results)} results")
            return results

        except ImportError:
            logger.error("duckduckgo-search not installed")
            return []
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []

    async def research(self, query: str) -> str:
        """Search and summarize results.

        Args:
            query: Research query

        Returns:
            Summary string
        """
        results = await self.search(query)

        if not results:
            return f"No results found for: {query}"

        # Format results for AI
        context_parts = []
        for r in results[:5]:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            context_parts.append(f"- {title}: {body} ({href})")

        context = "\n".join(context_parts)

        prompt = f"""Based on these search results, provide a helpful summary.

Query: {query}

Results:
{context}

Provide a concise, actionable summary (2-3 sentences). Include specific details if relevant."""

        summary = await self.ai.complete(prompt, max_tokens=300)

        if summary:
            return summary

        # AI failed, return basic result list
        basic_summary = f"Found {len(results)} results:\n"
        for r in results[:3]:
            basic_summary += f"- {r.get('title', 'No title')}\n"
        return basic_summary


# Singleton instance
_researcher: Optional[Researcher] = None


def get_researcher() -> Researcher:
    """Get or create the researcher singleton."""
    global _researcher
    if _researcher is None:
        _researcher = Researcher()
    return _researcher
