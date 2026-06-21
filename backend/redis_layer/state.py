"""
State persistence — mirrors lib/redis/state.ts.
Uses Redis when available, in-memory dict as fallback.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TypeVar

from redis_layer.client import get_redis_publisher, mark_redis_unavailable
from redis_layer.keys import EncounterKeys

logger = logging.getLogger(__name__)

T = TypeVar("T")

_memory_store: Dict[str, str] = {}


async def _get(key: str) -> Optional[str]:
    redis = get_redis_publisher()
    if redis:
        try:
            return await redis.get(key)
        except Exception as e:
            logger.warning("[state] redis get failed: %s", e)
            mark_redis_unavailable(str(e))
    return _memory_store.get(key)


async def _set(key: str, value: str) -> None:
    redis = get_redis_publisher()
    if redis:
        try:
            await redis.set(key, value)
            return
        except Exception as e:
            logger.warning("[state] redis set failed: %s", e)
            mark_redis_unavailable(str(e))
    _memory_store[key] = value


async def append_transcript(encounter_id: str, line: str) -> str:
    key = EncounterKeys.transcript(encounter_id)
    existing = (await _get(key)) or ""
    updated = f"{existing}\n{line}" if existing else line
    await _set(key, updated)
    return updated


async def append_buffer(encounter_id: str, text: str) -> str:
    key = EncounterKeys.buffer(encounter_id)
    existing = (await _get(key)) or ""
    updated = f"{existing} {text}" if existing else text
    await _set(key, updated)
    return updated


async def get_buffer(encounter_id: str) -> str:
    return (await _get(EncounterKeys.buffer(encounter_id))) or ""


async def clear_buffer(encounter_id: str) -> None:
    await _set(EncounterKeys.buffer(encounter_id), "")


async def get_transcript(encounter_id: str) -> str:
    return (await _get(EncounterKeys.transcript(encounter_id))) or ""


async def save_json(key: str, value: Any) -> None:
    await _set(key, json.dumps(value))


async def load_json(key: str) -> Optional[Any]:
    raw = await _get(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def add_to_set(key: str, member: str) -> bool:
    """Returns True if the member was newly added."""
    redis = get_redis_publisher()
    if redis:
        try:
            added = await redis.sadd(key, member)
            return added == 1
        except Exception as e:
            logger.warning("[state] redis sadd failed: %s", e)
            mark_redis_unavailable(str(e))

    set_key = f"set:{key}"
    existing = _memory_store.get(set_key)
    current: list = json.loads(existing) if existing else []
    if member in current:
        return False
    current.append(member)
    _memory_store[set_key] = json.dumps(current)
    return True


async def reset_encounter(encounter_id: str) -> None:
    keys = EncounterKeys.all_keys(encounter_id)
    redis = get_redis_publisher()
    if redis:
        try:
            if keys:
                await redis.delete(*keys)
            return
        except Exception as e:
            logger.warning("[state] redis delete failed: %s", e)
            mark_redis_unavailable(str(e))

    for key in keys:
        _memory_store.pop(key, None)
    _memory_store.pop(f"set:{EncounterKeys.researched_meds(encounter_id)}", None)
