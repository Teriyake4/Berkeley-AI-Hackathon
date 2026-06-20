import { NextResponse } from "next/server";
import { pingRedis, isRedisAvailable } from "@/lib/redis/client";
import { getClientCount } from "@/lib/sse/hub";

export const dynamic = "force-dynamic";

export async function GET() {
  const [redisOk] = await Promise.all([pingRedis()]);

  const status = {
    ok: true,
    timestamp: new Date().toISOString(),
    services: {
      redis: {
        configured: isRedisAvailable(),
        connected: redisOk,
        note: redisOk ? "connected" : "using in-memory fallback",
      },
      deepgram: {
        configured: Boolean(process.env.DEEPGRAM_API_KEY),
        note: process.env.DEEPGRAM_API_KEY
          ? "key present — live mic uses Deepgram"
          : "no key — live mic uses Web Speech API fallback",
      },
      anthropic: {
        configured: Boolean(process.env.ANTHROPIC_API_KEY),
        note: process.env.ANTHROPIC_API_KEY
          ? "key present — agents use Claude"
          : "no key — agents use heuristic fallbacks",
      },
      browserbase: {
        configured: Boolean(process.env.BROWSERBASE_API_KEY),
        note: process.env.BROWSERBASE_API_KEY
          ? "key present — research agent active"
          : "no key — research uses mock citations",
      },
    },
    sse: {
      connectedClients: getClientCount(),
    },
  };

  return NextResponse.json(status);
}
