"""
Audio events agent — detects prolonged silence during live encounters
and publishes audio.event to the bus.

Demo path: the injector fires audio beats directly from demo-scenario.json.
Live path: this agent subscribes to transcript.segment events and tracks
           the last-speech timestamp; if >30s passes with no new segment,
           it publishes a prolonged_silence event.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from bus import InMemoryBus, RedisBus
from events import EVENT_CHANNELS
from redis_layer.keys import ENCOUNTER_ID

logger = logging.getLogger(__name__)

SILENCE_THRESHOLD_S = 30


async def start_audio_events_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    state: Dict[str, Any] = {
        "last_speech": None,
        "encounter_active": False,
        "encounter_id": ENCOUNTER_ID,
    }
    monitor_task: asyncio.Task | None = None

    async def on_transcript(envelope: Dict[str, Any]) -> None:
        p = envelope.get("payload", {})
        state["last_speech"] = datetime.now(timezone.utc)
        state["encounter_id"] = p.get("encounterId", ENCOUNTER_ID)

    async def on_encounter(envelope: Dict[str, Any]) -> None:
        nonlocal monitor_task
        state["encounter_active"] = True
        state["last_speech"] = datetime.now(timezone.utc)
        if monitor_task is None or monitor_task.done():
            monitor_task = asyncio.create_task(_silence_monitor(bus, state))

    async def _silence_monitor(bus_ref: InMemoryBus | RedisBus, st: Dict[str, Any]) -> None:
        while st.get("encounter_active"):
            await asyncio.sleep(5)
            last = st.get("last_speech")
            if last is None:
                continue
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed >= SILENCE_THRESHOLD_S:
                enc_id = st.get("encounter_id", ENCOUNTER_ID)
                logger.info("[audio_events] prolonged_silence detected (%.0fs)", elapsed)
                await bus_ref.publish(EVENT_CHANNELS.AUDIO_EVENT, {
                    "encounterId": enc_id,
                    "type": "prolonged_silence",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": f"No speech for {int(elapsed)}s",
                })
                # Reset so we don't fire repeatedly for the same silence window
                st["last_speech"] = datetime.now(timezone.utc)

    unsub_transcript = await bus.subscribe(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, on_transcript)

    def stop() -> None:
        nonlocal monitor_task
        state["encounter_active"] = False
        unsub_transcript()
        if monitor_task and not monitor_task.done():
            monitor_task.cancel()

    logger.info("[audio_events] agent started")
    return stop
