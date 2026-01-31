"""Tests for AI engine."""

import pytest
from unittest.mock import patch

from backend.app.ai_engine import AIEngine


class TestAIEngine:
    """Test AIEngine class."""

    def test_init_default_timeout(self):
        """AIEngine initializes with default timeout."""
        engine = AIEngine()
        assert engine.timeout == 10.0

    def test_init_custom_timeout(self):
        """AIEngine accepts custom timeout."""
        engine = AIEngine(timeout=5.0)
        assert engine.timeout == 5.0

    def test_get_client_no_api_key(self):
        """_get_client returns None when no API key configured."""
        with patch("backend.app.ai_engine.settings") as mock_settings:
            mock_settings.azure_openai_api_key = ""
            engine = AIEngine()
            assert engine._get_client() is None

    @pytest.mark.asyncio
    async def test_complete_no_client(self):
        """complete returns None when client not available."""
        with patch("backend.app.ai_engine.settings") as mock_settings:
            mock_settings.azure_openai_api_key = ""
            engine = AIEngine()
            result = await engine.complete("test prompt")
            assert result is None

    @pytest.mark.asyncio
    async def test_complete_json_parses_valid_json(self):
        """complete_json parses valid JSON response."""
        engine = AIEngine()

        with patch.object(engine, "complete") as mock_complete:
            mock_complete.return_value = '{"intent": "next", "confidence": 0.9}'
            result = await engine.complete_json("test")

            assert result == {"intent": "next", "confidence": 0.9}

    @pytest.mark.asyncio
    async def test_complete_json_handles_markdown_wrapper(self):
        """complete_json strips markdown code blocks."""
        engine = AIEngine()

        with patch.object(engine, "complete") as mock_complete:
            mock_complete.return_value = '```json\n{"intent": "done"}\n```'
            result = await engine.complete_json("test")

            assert result == {"intent": "done"}

    @pytest.mark.asyncio
    async def test_complete_json_returns_none_on_invalid_json(self):
        """complete_json returns None for invalid JSON."""
        engine = AIEngine()

        with patch.object(engine, "complete") as mock_complete:
            mock_complete.return_value = "not valid json"
            result = await engine.complete_json("test")

            assert result is None

    @pytest.mark.asyncio
    async def test_complete_json_returns_none_when_complete_fails(self):
        """complete_json returns None when complete returns None."""
        engine = AIEngine()

        with patch.object(engine, "complete") as mock_complete:
            mock_complete.return_value = None
            result = await engine.complete_json("test")

            assert result is None
