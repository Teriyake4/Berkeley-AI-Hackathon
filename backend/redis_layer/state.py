"""
State persistence — mirrors lib/redis/state.ts.
Uses Redis when available, in-memory dict as fallback.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

from redis_layer.client import get_redis_publisher, mark_redis_unavailable
from redis_layer.keys import ACTIVE_SESSION, SESSIONS_INDEX, EncounterKeys

logger = logging.getLogger(__name__)

T = TypeVar("T")

_memory_store: Dict[str, str] = {}
_memory_lists: Dict[str, List[str]] = {}
_memory_zsets: Dict[str, Dict[str, float]] = {}

# Events that count as session activity (empty Live clicks do not register).
_ACTIVITY_CHANNELS = frozenset({
    "transcript.segment",
    "vision.captured",
    "telemetry.updated",
    "audio.event",
    "facts.extracted",
    "timeline.updated",
    "safety.flagged",
    "note.updated",
    "research.completed",
    "handoff.generated",
})


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


async def _zadd(index_key: str, score: float, member: str) -> None:
    redis = get_redis_publisher()
    if redis:
        try:
            await redis.zadd(index_key, {member: score})
            return
        except Exception as e:
            logger.warning("[state] redis zadd failed: %s", e)
            mark_redis_unavailable(str(e))
    zset = _memory_zsets.setdefault(index_key, {})
    zset[member] = score


async def _zrevrange(index_key: str) -> List[tuple[str, float]]:
    redis = get_redis_publisher()
    if redis:
        try:
            raw = await redis.zrevrange(index_key, 0, -1, withscores=True)
            return [(m.decode() if isinstance(m, bytes) else str(m), float(s)) for m, s in raw]
        except Exception as e:
            logger.warning("[state] redis zrevrange failed: %s", e)
            mark_redis_unavailable(str(e))
    zset = _memory_zsets.get(index_key, {})
    return sorted(zset.items(), key=lambda x: x[1], reverse=True)


async def _rpush(key: str, value: str) -> None:
    redis = get_redis_publisher()
    if redis:
        try:
            await redis.rpush(key, value)
            return
        except Exception as e:
            logger.warning("[state] redis rpush failed: %s", e)
            mark_redis_unavailable(str(e))
    _memory_lists.setdefault(key, []).append(value)


async def _zrem(index_key: str, member: str) -> None:
    redis = get_redis_publisher()
    if redis:
        try:
            await redis.zrem(index_key, member)
            return
        except Exception as e:
            logger.warning("[state] redis zrem failed: %s", e)
            mark_redis_unavailable(str(e))
    zset = _memory_zsets.get(index_key)
    if zset:
        zset.pop(member, None)


async def append_transcript(encounter_id: str, line: str) -> str:
    key = EncounterKeys.transcript(encounter_id)
    existing = (await _get(key)) or ""
    updated = f"{existing}\n{line}" if existing else line
    await _set(key, updated)
    return updated


async def append_transcript_line(
    encounter_id: str,
    speaker: str,
    text: str,
    timestamp: str,
) -> None:
    await ensure_session_saved(encounter_id, activity_at=timestamp)
    await append_transcript(encounter_id, f"[{speaker}] {text}")
    key = EncounterKeys.transcript_lines(encounter_id)
    lines = (await load_json(key)) or []
    lines.append({"speaker": speaker, "text": text, "timestamp": timestamp})
    await save_json(key, lines)


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


async def append_event_log(
    encounter_id: str,
    channel: str,
    payload: Dict[str, Any],
    at: Optional[str] = None,
) -> None:
    meta = await get_session_meta(encounter_id)
    if meta and meta.get("mode") == "demo":
        return
    ts = at or datetime.now(timezone.utc).isoformat()
    if channel in _ACTIVITY_CHANNELS:
        payload_ts = payload.get("timestamp") or payload.get("extractedAt") or payload.get("flaggedAt")
        await ensure_session_saved(encounter_id, activity_at=payload_ts or ts)
    key = EncounterKeys.events(encounter_id)
    entry = {
        "channel": channel,
        "payload": payload,
        "at": ts,
    }
    await _rpush(key, json.dumps(entry))


async def get_session_meta(encounter_id: str) -> Optional[Dict[str, Any]]:
    return await load_json(EncounterKeys.meta(encounter_id))


async def is_session_registered(encounter_id: str) -> bool:
    meta = await get_session_meta(encounter_id)
    return meta is not None and meta.get("status") in ("active", "completed")


async def start_pending_session(encounter_id: str, mode: str) -> None:
    """Track a new encounter locally; not indexed until first activity."""
    created_at = datetime.now(timezone.utc).isoformat()
    await _set(ACTIVE_SESSION, encounter_id)
    await save_json(
        EncounterKeys.meta(encounter_id),
        {"mode": mode, "status": "pending", "createdAt": created_at},
    )


async def ensure_session_saved(
    encounter_id: str,
    activity_at: Optional[str] = None,
) -> bool:
    """Promote a pending session to the saved session index on first activity."""
    if await is_session_registered(encounter_id):
        return True
    meta = await get_session_meta(encounter_id)
    if not meta or meta.get("status") != "pending":
        return False
    mode = meta.get("mode", "live")
    if mode == "demo":
        return False
    started_at = activity_at or datetime.now(timezone.utc).isoformat()
    await register_session(encounter_id, mode, started_at)
    return True


async def register_session(encounter_id: str, mode: str, started_at: str) -> None:
    score_ms = datetime.fromisoformat(started_at.replace("Z", "+00:00")).timestamp() * 1000
    await _set(EncounterKeys.encounter_start(encounter_id), started_at)
    await save_json(
        EncounterKeys.meta(encounter_id),
        {"startedAt": started_at, "mode": mode, "status": "active"},
    )
    await _zadd(SESSIONS_INDEX, score_ms, encounter_id)
    await _set(ACTIVE_SESSION, encounter_id)


async def discard_session(encounter_id: str) -> None:
    """Remove an unregistered / empty session and all working keys."""
    await reset_encounter(encounter_id)
    await _set(EncounterKeys.encounter_start(encounter_id), "")
    await _set(EncounterKeys.meta(encounter_id), "")
    await _zrem(SESSIONS_INDEX, encounter_id)
    active = await _get(ACTIVE_SESSION)
    if active == encounter_id:
        await _set(ACTIVE_SESSION, "")


async def complete_session(
    encounter_id: str,
    ended_at: Optional[str] = None,
) -> None:
    meta = await get_session_meta(encounter_id)
    if not meta:
        return
    if meta.get("status") == "completed":
        return
    ended = ended_at or datetime.now(timezone.utc).isoformat()
    meta["status"] = "completed"
    meta["endedAt"] = ended
    await save_json(EncounterKeys.meta(encounter_id), meta)
    active = await _get(ACTIVE_SESSION)
    if active == encounter_id:
        await _set(ACTIVE_SESSION, "")


async def finalize_session(encounter_id: str) -> None:
    """End a session — discard demo/pending; complete live sessions with activity."""
    meta = await get_session_meta(encounter_id)
    if not meta:
        return
    if meta.get("mode") == "demo" or meta.get("status") == "pending":
        await discard_session(encounter_id)
        return
    await complete_session(encounter_id)


async def finalize_active_session() -> None:
    active = await _get(ACTIVE_SESSION)
    if active:
        await finalize_session(active)


async def list_sessions() -> List[Dict[str, Any]]:
    entries = await _zrevrange(SESSIONS_INDEX)
    sessions: List[Dict[str, Any]] = []
    for encounter_id, _score in entries:
        meta = await get_session_meta(encounter_id) or {}
        if meta.get("mode") == "demo":
            continue
        started_at = meta.get("startedAt") or (await _get(EncounterKeys.encounter_start(encounter_id)))
        sessions.append(
            {
                "encounterId": encounter_id,
                "startedAt": started_at,
                "mode": meta.get("mode", "unknown"),
                "status": meta.get("status", "unknown"),
                "endedAt": meta.get("endedAt"),
            }
        )
    return sessions


def _encounter_id_from_meta_key(key: str) -> Optional[str]:
    # encounter:{id}:meta
    parts = key.split(":")
    if len(parts) >= 3 and parts[0] == "encounter" and parts[-1] == "meta":
        return ":".join(parts[1:-1])
    return None


async def purge_all_demo_sessions() -> int:
    """Remove all demo sessions from the index and delete their Redis keys."""
    purged_ids: set[str] = set()

    for encounter_id, _score in await _zrevrange(SESSIONS_INDEX):
        meta = await get_session_meta(encounter_id) or {}
        if meta.get("mode") == "demo":
            purged_ids.add(encounter_id)

    redis = get_redis_publisher()
    if redis:
        try:
            async for key in redis.scan_iter(match="encounter:*:meta"):
                key_str = key.decode() if isinstance(key, bytes) else str(key)
                encounter_id = _encounter_id_from_meta_key(key_str)
                if not encounter_id:
                    continue
                meta = await load_json(key_str)
                if meta and meta.get("mode") == "demo":
                    purged_ids.add(encounter_id)
        except Exception as e:
            logger.warning("[state] demo purge scan failed: %s", e)
    else:
        for key in list(_memory_store.keys()):
            if not key.endswith(":meta"):
                continue
            encounter_id = _encounter_id_from_meta_key(key)
            if not encounter_id:
                continue
            meta = await load_json(key)
            if meta and meta.get("mode") == "demo":
                purged_ids.add(encounter_id)

    for encounter_id in purged_ids:
        await discard_session(encounter_id)

    return len(purged_ids)


def _parse_transcript_lines(raw: str) -> List[Dict[str, str]]:
    lines: List[Dict[str, str]] = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        match = re.match(r"^\[(.+?)\]\s*(.*)$", line)
        if match:
            lines.append(
                {
                    "speaker": match.group(1),
                    "text": match.group(2),
                    "timestamp": "",
                }
            )
    return lines


async def get_encounter_snapshot(encounter_id: str) -> Optional[Dict[str, Any]]:
    meta = await get_session_meta(encounter_id)
    if not meta or meta.get("status") == "pending" or meta.get("mode") == "demo":
        return None

    started_at = (await _get(EncounterKeys.encounter_start(encounter_id))) or meta.get("startedAt")

    transcript_lines = await load_json(EncounterKeys.transcript_lines(encounter_id))
    if not transcript_lines:
        raw = await get_transcript(encounter_id)
        transcript_lines = _parse_transcript_lines(raw) if raw else []

    facts = await load_json(EncounterKeys.facts(encounter_id))
    timeline = await load_json(EncounterKeys.timeline(encounter_id)) or []
    safety_flags = await load_json(EncounterKeys.safety_flags(encounter_id)) or []
    soap = await load_json(EncounterKeys.soap(encounter_id))
    research_raw = await load_json(EncounterKeys.research(encounter_id)) or []
    handoff = await load_json(EncounterKeys.handoff(encounter_id))
    vision_items = await load_json(EncounterKeys.vision_items(encounter_id)) or []

    return {
        "encounterId": encounter_id,
        "startedAt": started_at,
        "meta": meta,
        "transcript": transcript_lines,
        "facts": facts,
        "timeline": timeline,
        "safetyFlags": safety_flags,
        "soap": soap,
        "research": research_raw,
        "handoff": handoff,
        "visionItems": vision_items,
    }


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
        _memory_lists.pop(key, None)
    _memory_store.pop(f"set:{EncounterKeys.researched_meds(encounter_id)}", None)
