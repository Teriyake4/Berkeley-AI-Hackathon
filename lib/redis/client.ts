import Redis from "ioredis";

let publisher: Redis | null = null;
let subscriber: Redis | null = null;
let redisUnavailable = false;

function makeClient(url: string, name: string): Redis | null {
  try {
    const client = new Redis(url, {
      maxRetriesPerRequest: 2,
      enableReadyCheck: true,
      lazyConnect: true,
      connectTimeout: 5000,
      retryStrategy(times) {
        if (times > 3) {
          console.warn(`[redis/${name}] giving up after ${times} retries — using in-memory fallback`);
          redisUnavailable = true;
          return null; // stop retrying
        }
        return Math.min(times * 200, 1000);
      },
    });

    client.on("error", (err) => {
      // Only log once to avoid log spam
      if (!redisUnavailable) {
        console.warn(`[redis/${name}] connection error — using in-memory fallback:`, err.message);
      }
      redisUnavailable = true;
    });

    client.on("connect", () => {
      console.log(`[redis/${name}] connected`);
      redisUnavailable = false;
    });

    client.on("reconnecting", () => {
      console.log(`[redis/${name}] reconnecting…`);
    });

    return client;
  } catch (err) {
    console.warn(`[redis/${name}] failed to create client:`, (err as Error).message);
    return null;
  }
}

export function isRedisAvailable(): boolean {
  return Boolean(process.env.REDIS_URL) && !redisUnavailable;
}

export function getRedisPublisher(): Redis | null {
  if (!process.env.REDIS_URL || redisUnavailable) return null;
  if (!publisher) {
    publisher = makeClient(process.env.REDIS_URL, "publisher");
  }
  return publisher;
}

export function getRedisSubscriber(): Redis | null {
  if (!process.env.REDIS_URL || redisUnavailable) return null;
  if (!subscriber) {
    subscriber = makeClient(process.env.REDIS_URL, "subscriber");
  }
  return subscriber;
}

export async function pingRedis(): Promise<boolean> {
  try {
    const client = getRedisPublisher();
    if (!client) return false;
    const res = await client.ping();
    return res === "PONG";
  } catch {
    return false;
  }
}
