import { readFileSync } from "fs";
import { join } from "path";
import type { EventBus } from "@/lib/bus";
import { EVENT_CHANNELS, type Speaker } from "@/lib/events";
import { appendTranscript } from "@/lib/redis/state";

interface DemoBeat {
  id: string;
  delayMs: number;
  speaker: Speaker;
  text: string;
}

interface DemoScenario {
  encounterId: string;
  beats: DemoBeat[];
}

const activeInjectors = new Map<string, AbortController>();

export function stopDemo(encounterId: string): void {
  activeInjectors.get(encounterId)?.abort();
  activeInjectors.delete(encounterId);
}

export function isDemoRunning(encounterId: string): boolean {
  return activeInjectors.has(encounterId);
}

function loadScenario(): DemoScenario {
  const scenarioPath = join(process.cwd(), "scripts", "demo-scenario.json");
  try {
    return JSON.parse(readFileSync(scenarioPath, "utf-8")) as DemoScenario;
  } catch (err) {
    console.error("[demo] failed to load demo-scenario.json:", err);
    // Return a minimal inline fallback so demo still works
    return {
      encounterId: "demo-encounter-001",
      beats: [
        { id: "b1", delayMs: 0, speaker: "doctor", text: "Good morning. What brings you in today?" },
        { id: "b2", delayMs: 4000, speaker: "patient", text: "I have chest pain and I take warfarin." },
        { id: "b3", delayMs: 9000, speaker: "doctor", text: "Any shortness of breath? Age?" },
        { id: "b4", delayMs: 13000, speaker: "patient", text: "I'm 67. A little short of breath, left arm pain too." },
      ],
    };
  }
}

export async function runDemoScenario(
  bus: EventBus,
  encounterId: string
): Promise<void> {
  stopDemo(encounterId); // cancel any running replay for this encounter

  const controller = new AbortController();
  activeInjectors.set(encounterId, controller);

  const scenario = loadScenario();
  const beats = scenario.beats;

  console.log(`[demo] starting replay for ${encounterId} (${beats.length} beats)`);

  let elapsed = 0;
  for (const beat of beats) {
    if (controller.signal.aborted) {
      console.log("[demo] replay aborted");
      return;
    }

    const wait = beat.delayMs - elapsed;
    if (wait > 0) {
      try {
        await sleep(wait, controller.signal);
      } catch {
        return; // aborted during sleep
      }
    }
    elapsed = beat.delayMs;

    if (controller.signal.aborted) return;

    const timestamp = new Date().toISOString();
    try {
      await appendTranscript(encounterId, `[${beat.speaker}] ${beat.text}`);
      await bus.publish(EVENT_CHANNELS.TRANSCRIPT_SEGMENT, {
        encounterId,
        text: beat.text,
        speaker: beat.speaker,
        timestamp,
      });
      console.log(`[demo] beat ${beat.id}: ${beat.speaker}: ${beat.text.slice(0, 60)}`);
    } catch (err) {
      console.error(`[demo] failed to publish beat ${beat.id}:`, err);
      // Continue with remaining beats
    }
  }

  activeInjectors.delete(encounterId);
  console.log("[demo] replay complete");
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new Error("aborted"));
    });
  });
}
