"""
Agent runtime — mirrors lib/agents/runtime.ts.
Ensures all agents are started exactly once.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

_started = False
_starting: Optional[asyncio.Task] = None
_stop_fns: List[Callable[[], None]] = []


async def ensure_agents_started() -> None:
    global _started, _starting

    if _started:
        return
    if _starting is not None:
        await _starting
        return

    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()
    _starting = future  # type: ignore[assignment]

    try:
        from bus import get_event_bus
        from agents.extraction import start_extraction_agent
        from agents.timeline import start_timeline_agent
        from agents.safety import start_safety_agent
        from agents.documentation import start_documentation_agent
        from agents.research import start_research_agent
        from agents.handoff import start_handoff_agent
        from agents.vision import start_vision_agent

        bus = get_event_bus()
        stops = await asyncio.gather(
            start_extraction_agent(bus),
            start_timeline_agent(bus),
            start_safety_agent(bus),
            start_documentation_agent(bus),
            start_research_agent(bus),
            start_handoff_agent(bus),
            start_vision_agent(bus),
        )
        _stop_fns.extend(stops)
        _started = True
        logger.info("[runtime] All agents started")
    except Exception as e:
        logger.error("[runtime] Failed to start agents — continuing without agents: %s", e)
        _started = True  # don't retry on every request
    finally:
        if not future.done():
            future.set_result(None)


async def stop_all_agents() -> None:
    global _started, _starting, _stop_fns
    for fn in _stop_fns:
        try:
            fn()
        except Exception:
            pass
    _stop_fns.clear()
    _started = False
    _starting = None
