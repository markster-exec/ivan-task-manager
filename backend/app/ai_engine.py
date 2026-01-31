"""Azure OpenAI wrapper with timeout and error handling.

Provides a simple interface for AI completions with graceful fallback.
"""

import asyncio
import json
import logging
from typing import Optional

from .config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class AIEngine:
    """Azure OpenAI wrapper with timeout and error handling."""

    def __init__(self, timeout: float = 10.0):
        """Initialize AI engine.

        Args:
            timeout: Maximum seconds to wait for API response
        """
        self.timeout = timeout
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            if not settings.azure_openai_api_key:
                return None

            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                api_version="2024-02-15-preview",
                azure_endpoint=settings.azure_openai_endpoint,
            )
        return self._client

    async def complete(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.0,
    ) -> Optional[str]:
        """Get text completion with timeout.

        Args:
            prompt: The prompt to complete
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            Completion text, or None on failure
        """
        client = self._get_client()
        if not client:
            logger.warning("AI engine not configured (no API key)")
            return None

        try:
            # Run sync API in thread pool with timeout
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model=settings.azure_openai_deployment,
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    ),
                ),
                timeout=self.timeout,
            )

            content = response.choices[0].message.content
            if content:
                return content.strip()
            return None

        except asyncio.TimeoutError:
            logger.warning(f"AI completion timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.warning(f"AI completion failed: {e}")
            return None

    async def complete_json(
        self,
        prompt: str,
        max_tokens: int = 500,
    ) -> Optional[dict]:
        """Get JSON completion with parsing.

        Args:
            prompt: The prompt (should request JSON output)
            max_tokens: Maximum tokens in response

        Returns:
            Parsed JSON dict, or None on failure/invalid JSON
        """
        # Add JSON instruction to prompt
        json_prompt = prompt + "\n\nRespond with valid JSON only, no markdown."

        text = await self.complete(json_prompt, max_tokens=max_tokens)
        if not text:
            return None

        try:
            # Clean up common issues
            text = text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI JSON response: {e}")
            logger.debug(f"Raw response: {text}")
            return None


# Singleton instance
_engine: Optional[AIEngine] = None


def get_ai_engine() -> AIEngine:
    """Get or create the AI engine singleton."""
    global _engine
    if _engine is None:
        _engine = AIEngine()
    return _engine
