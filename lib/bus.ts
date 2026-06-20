/**
 * Event bus — Redis when available, in-memory fallback otherwise.
 *
 * Design:
 * - `broadcastToClients` (SSE fan-out) is called exactly once per publish,
 *   directly in `publish()`. The Redis subscriber handler only dispatches to
 *   local agent handlers — it does NOT re-broadcast, avoiding double SSE delivery.
 * - Local agent handlers are always called directly in `publish()` for
 *   zero-latency dispatch in the single-process hackathon setup. Redis pub/sub
 *   is kept for state consistency and future multi-instance use.
 */

import type { EventChannel, EventEnvelope, EventPayloadMap } from "./events";
import { pubsubChannel } from "./redis/keys";
import { getRedisPublisher, getRedisSubscriber } from "./redis/client";
import { broadcastToClients } from "./sse/hub";

export type EventHandler<C extends EventChannel> = (
  envelope: EventEnvelope<C>
) => void | Promise<void>;

export interface EventBus {
  publish<C extends EventChannel>(
    channel: C,
    payload: EventPayloadMap[C]
  ): Promise<void>;

  subscribe<C extends EventChannel>(
    channel: C,
    handler: EventHandler<C>
  ): Promise<() => void>;
}

function createInMemoryBus(): EventBus {
  const listeners = new Map<string, Set<EventHandler<EventChannel>>>();

  return {
    async publish(channel, payload) {
      const envelope = { channel, payload } as EventEnvelope;
      broadcastToClients(envelope);
      const handlers = listeners.get(channel);
      if (!handlers) return;
      const results = [...handlers].map((h) =>
        Promise.resolve().then(() => h(envelope)).catch((err) =>
          console.error(`[bus] handler error on ${channel}:`, err)
        )
      );
      await Promise.all(results);
    },

    async subscribe(channel, handler) {
      if (!listeners.has(channel)) listeners.set(channel, new Set());
      listeners.get(channel)!.add(handler as EventHandler<EventChannel>);
      return () => listeners.get(channel)?.delete(handler as EventHandler<EventChannel>);
    },
  };
}

function createRedisBus(): EventBus {
  const localHandlers = new Map<string, Set<EventHandler<EventChannel>>>();
  const subscriber = getRedisSubscriber();
  const publisher = getRedisPublisher();

  if (!subscriber || !publisher) return createInMemoryBus();

  // Only dispatch to local handlers — do NOT call broadcastToClients here.
  // SSE broadcasting is handled exactly once in publish() below.
  subscriber.on("message", async (_redisChannel, message) => {
    try {
      const envelope = JSON.parse(message) as EventEnvelope;
      const handlers = localHandlers.get(envelope.channel);
      if (!handlers) return;
      const results = [...handlers].map((h) =>
        Promise.resolve().then(() => h(envelope)).catch((err) =>
          console.error(`[bus/redis] handler error on ${envelope.channel}:`, err)
        )
      );
      await Promise.all(results);
    } catch (err) {
      console.error("[bus/redis] failed to parse message:", err);
    }
  });

  subscriber.on("error", (err) => {
    console.warn("[bus/redis] subscriber error:", err.message);
  });

  return {
    async publish(channel, payload) {
      const envelope = { channel, payload } as EventEnvelope;

      // 1. Fan out to SSE clients immediately (single broadcast).
      broadcastToClients(envelope);

      // 2. Dispatch to local agent handlers directly (no Redis round-trip latency).
      const handlers = localHandlers.get(channel);
      if (handlers) {
        const results = [...handlers].map((h) =>
          Promise.resolve().then(() => h(envelope)).catch((err) =>
            console.error(`[bus] handler error on ${channel}:`, err)
          )
        );
        await Promise.all(results);
      }

      // 3. Publish to Redis for persistence / future multi-instance use.
      try {
        await publisher.publish(pubsubChannel(channel), JSON.stringify(envelope));
      } catch (err) {
        console.warn("[bus/redis] publish failed (continuing):", (err as Error).message);
      }
    },

    async subscribe(channel, handler) {
      if (!localHandlers.has(channel)) {
        localHandlers.set(channel, new Set());
        try {
          await subscriber.subscribe(pubsubChannel(channel));
        } catch (err) {
          console.warn(`[bus/redis] subscribe failed for ${channel}:`, (err as Error).message);
        }
      }
      localHandlers.get(channel)!.add(handler as EventHandler<EventChannel>);
      return () => localHandlers.get(channel)?.delete(handler as EventHandler<EventChannel>);
    },
  };
}

let busInstance: EventBus | null = null;

export function getEventBus(): EventBus {
  if (!busInstance) {
    const pub = getRedisPublisher();
    busInstance = pub ? createRedisBus() : createInMemoryBus();
  }
  return busInstance;
}

/** Resets the singleton — used in tests and hot-reload recovery. */
export function resetEventBus(): void {
  busInstance = null;
}

export { createInMemoryBus };
