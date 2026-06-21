"""
LLM wrapper — Anthropic Claude primary, NVIDIA NIM fallback.
Retries once on rate-limit (429). Returns None on any unrecoverable error
so agents can fall through to heuristic fallbacks.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional, TypeVar

from llm_parse import parse_json_from_llm_text
from nim import call_nim_json, has_nim

logger = logging.getLogger(__name__)

T = TypeVar("T")

_client = None

JSON_SYSTEM_SUFFIX = (
    "\n\nIMPORTANT: Respond with ONLY the raw JSON — no markdown fences, no explanation."
)


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


def has_claude() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def has_llm() -> bool:
    return has_claude() or has_nim()


HAIKU_MODEL = "claude-haiku-4-5"
SONNET_MODEL = "claude-sonnet-4-6"

# Per-agent model/token overrides.
# Safety uses Sonnet — it's the highest-stakes reasoning in the system.
# Handoff uses Sonnet for quality. Timeline/extraction use Haiku for speed.
AGENT_MODELS: dict[str, str] = {}
AGENT_MAX_TOKENS: dict[str, int] = {
    "handoff": 4096,
    "safety": 2048,
}


def _refresh_agent_models() -> None:
    AGENT_MODELS.clear()
    AGENT_MODELS.update({
        "safety": os.environ.get("ANTHROPIC_MODEL_SAFETY", SONNET_MODEL),
        "handoff": os.environ.get("ANTHROPIC_MODEL_HANDOFF", SONNET_MODEL),
        "timeline": os.environ.get("ANTHROPIC_MODEL_TIMELINE", HAIKU_MODEL),
    })


_refresh_agent_models()


def _claude_model(agent_name: str) -> str:
    _refresh_agent_models()
    return AGENT_MODELS.get(agent_name) or os.environ.get("ANTHROPIC_MODEL", HAIKU_MODEL)


def _max_tokens_for(agent_name: str) -> int:
    return AGENT_MAX_TOKENS.get(agent_name, 2048)


async def _call_claude_json(system: str, user: str, agent_name: str) -> Optional[Any]:
    client = _get_client()
    if not client:
        return None

    full_system = system + JSON_SYSTEM_SUFFIX
    model = _claude_model(agent_name)
    max_tokens = _max_tokens_for(agent_name)

    for attempt in range(2):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=full_system,
                messages=[{"role": "user", "content": user}],
            )

            raw = ""
            if response.content and response.content[0].type == "text":
                raw = response.content[0].text.strip()

            return parse_json_from_llm_text(raw)

        except Exception as e:
            status = getattr(e, "status_code", None)
            if status == 429 and attempt == 0:
                await asyncio.sleep(2.0)
                continue
            logger.warning("[claude/%s] error (model=%s): %s", agent_name, model, e)
            return None

    return None


async def call_claude_json(system: str, user: str, agent_name: str) -> Optional[Any]:
    """
    Call Claude, then NVIDIA NIM if Claude is unavailable or fails.
    Returns None if neither provider yields parseable JSON.
    """
    if has_claude():
        result = await _call_claude_json(system, user, agent_name)
        if result is not None:
            return result
        if has_nim():
            logger.info("[llm/%s] Claude failed — trying NVIDIA NIM", agent_name)

    if has_nim():
        return await call_nim_json(system, user, agent_name)

    return None
