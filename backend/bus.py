"""
Event bus — Redis when available, in-memory fallback otherwise.

Design mirrors the TypeScript original:
- broadcastToClients (SSE fan-out) is called exactly once per publish, directly
  in publish(). The Redis subscriber handler only dispatches to local agent
  handlers to avoid double SSE delivery.
- Local agent handlers are always called directly in publish() for zero-latency
  dispatch.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, Set

from events import EVENT_CHANNELS

logger = logging.getLogger(__name__)

EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


async def _persist_event_log(channel: str, payload: Any) -> None:
    from events import to_dict

    data = to_dict(payload)
    encounter_id = data.get("encounterId") if isinstance(data, dict) else None
    if not encounter_id:
        return
    try:
        from redis_layer.state import append_event_log

        await append_event_log(encounter_id, channel, data)
    except Exception as e:
        logger.warning("[bus] event log append failed: %s", e)


class InMemoryBus:
    def __init__(self) -> None:
        self._listeners: Dict[str, Set[EventHandler]] = {}

    async def publish(self, channel: str, payload: Any) -> None:
        from sse.hub import broadcast_to_clients
        from events import to_dict

        envelope = {"channel": channel, "payload": to_dict(payload)}
        broadcast_to_clients(envelope)
        await _persist_event_log(channel, payload)

        handlers = list(self._listeners.get(channel, set()))
        tasks = []
        for h in handlers:
            tasks.append(asyncio.create_task(_safe_call(h, envelope, channel)))
        if tasks:
            await asyncio.gather(*tasks)

    async def subscribe(self, channel: str, handler: EventHandler) -> Callable[[], None]:
        if channel not in self._listeners:
            self._listeners[channel] = set()
        self._listeners[channel].add(handler)
        return lambda: self._listeners.get(channel, set()).discard(handler)


class RedisBus:
    def __init__(self, publisher, subscriber) -> None:
        self._publisher = publisher
        self._subscriber = subscriber
        self._local_handlers: Dict[str, Set[EventHandler]] = {}
        self._pubsub = None
        self._started = False

    async def _get_pubsub(self):
        if self._pubsub is None:
            self._pubsub = self._subscriber.pubsub()
        return self._pubsub

    async def _start_listener(self) -> None:
        if self._started:
            return
        self._started = True
        asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        pubsub = await self._get_pubsub()
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    try:
                        envelope = json.loads(msg["data"])
                        ch = envelope.get("channel", "")
                        handlers = list(self._local_handlers.get(ch, set()))
                        tasks = [asyncio.create_task(_safe_call(h, envelope, ch)) for h in handlers]
                        if tasks:
                            await asyncio.gather(*tasks)
                    except Exception as e:
                        logger.warning("[bus/redis] failed to parse message: %s", e)
                await asyncio.sleep(0)
        except Exception as e:
            logger.warning("[bus/redis] listener error: %s", e)

    async def publish(self, channel: str, payload: Any) -> None:
        from sse.hub import broadcast_to_clients
        from events import to_dict
        from redis_layer.keys import pubsub_channel

        envelope = {"channel": channel, "payload": to_dict(payload)}

        # 1. Fan out to SSE clients immediately
        broadcast_to_clients(envelope)
        await _persist_event_log(channel, payload)

        # 2. Dispatch to local agent handlers directly
        handlers = list(self._local_handlers.get(channel, set()))
        tasks = [asyncio.create_task(_safe_call(h, envelope, channel)) for h in handlers]
        if tasks:
            await asyncio.gather(*tasks)

        # 3. Publish to Redis for persistence / future multi-instance use
        try:
            await self._publisher.publish(pubsub_channel(channel), json.dumps(envelope))
        except Exception as e:
            logger.warning("[bus/redis] publish failed (continuing): %s", e)

    async def subscribe(self, channel: str, handler: EventHandler) -> Callable[[], None]:
        from redis_layer.keys import pubsub_channel

        if channel not in self._local_handlers:
            self._local_handlers[channel] = set()
            try:
                pubsub = await self._get_pubsub()
                await pubsub.subscribe(pubsub_channel(channel))
            except Exception as e:
                logger.warning("[bus/redis] subscribe failed for %s: %s", channel, e)

        await self._start_listener()
        self._local_handlers[channel].add(handler)
        return lambda: self._local_handlers.get(channel, set()).discard(handler)


async def _safe_call(handler: EventHandler, envelope: Dict, channel: str) -> None:
    try:
        await handler(envelope)
    except Exception as e:
        logger.error("[bus] handler error on %s: %s", channel, e)


# ─── Singleton ──────────────────────────────────────────────────────────────────

_bus_instance: InMemoryBus | RedisBus | None = None


def get_event_bus() -> InMemoryBus | RedisBus:
    global _bus_instance
    if _bus_instance is None:
        from redis_layer.client import get_redis_publisher, get_redis_subscriber
        pub = get_redis_publisher()
        if pub:
            sub = get_redis_subscriber()
            _bus_instance = RedisBus(pub, sub)
        else:
            _bus_instance = InMemoryBus()
    return _bus_instance


def reset_event_bus() -> None:
    global _bus_instance
    _bus_instance = None
