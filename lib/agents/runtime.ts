import { getEventBus } from "@/lib/bus";
import { startAllAgents } from "@/lib/agents";

let started = false;
let starting: Promise<void> | null = null;
let stopAgents: (() => void) | null = null;

export async function ensureAgentsStarted(): Promise<void> {
  if (started) return;
  if (starting) return starting;

  starting = (async () => {
    try {
      const bus = getEventBus();
      stopAgents = await startAllAgents(bus);
      started = true;
      console.log("[runtime] All agents started");
    } catch (err) {
      console.error("[runtime] Failed to start agents — continuing without agents:", err);
      started = true; // don't retry on every request
    }
  })();

  return starting;
}

/** Gracefully stops all agents (used in tests and hot-reload). */
export async function stopAllAgents(): Promise<void> {
  if (stopAgents) {
    stopAgents();
    stopAgents = null;
  }
  started = false;
  starting = null;
}
