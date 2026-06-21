"""
Redis client — mirrors lib/redis/client.ts.
Uses redis.asyncio with graceful fallback when Redis is unavailable.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_publisher = None
_subscriber = None
_redis_unavailable = False


def mark_redis_unavailable(reason: str = "") -> None:
    """Stop retrying Redis after a failure; state/bus use in-memory fallback."""
    global _redis_unavailable, _publisher, _subscriber
    if _redis_unavailable:
        return
    _redis_unavailable = True
    _publisher = None
    _subscriber = None
    suffix = f": {reason}" if reason else ""
    logger.warning("[redis] unavailable — using in-memory fallback%s", suffix)


def _make_client(url: str, name: str):
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=False,
        )
        return client
    except Exception as e:
        logger.warning("[redis/%s] failed to create client: %s", name, e)
        return None


def is_redis_available() -> bool:
    return bool(os.environ.get("REDIS_URL")) and not _redis_unavailable


def get_redis_publisher():
    global _publisher, _redis_unavailable
    if not os.environ.get("REDIS_URL") or _redis_unavailable:
        return None
    if _publisher is None:
        _publisher = _make_client(os.environ["REDIS_URL"], "publisher")
    return _publisher


def get_redis_subscriber():
    global _subscriber, _redis_unavailable
    if not os.environ.get("REDIS_URL") or _redis_unavailable:
        return None
    if _subscriber is None:
        _subscriber = _make_client(os.environ["REDIS_URL"], "subscriber")
    return _subscriber


async def ping_redis() -> bool:
    try:
        client = get_redis_publisher()
        if not client:
            return False
        result = await client.ping()
        return result is True or result == b"PONG" or result == "PONG"
    except Exception as e:
        mark_redis_unavailable(str(e))
        return False
