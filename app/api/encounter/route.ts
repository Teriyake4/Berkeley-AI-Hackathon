import { NextResponse } from "next/server";
import { ensureAgentsStarted } from "@/lib/agents/runtime";
import { getEventBus } from "@/lib/bus";
import { runDemoScenario, stopDemo, isDemoRunning } from "@/lib/demo/injector";
import { resetEncounter } from "@/lib/redis/state";
import { ENCOUNTER_ID } from "@/lib/redis/keys";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  await ensureAgentsStarted();

  const body = await request.json().catch(() => ({}));
  const mode = body.mode === "live" ? "live" : "demo";
  const encounterId = (body.encounterId as string) ?? ENCOUNTER_ID;

  await resetEncounter(encounterId);
  stopDemo(encounterId);

  if (mode === "demo") {
    const bus = getEventBus();
    runDemoScenario(bus, encounterId).catch((err) => {
      if (err?.message !== "aborted") console.error("[encounter] demo error:", err);
    });
  }

  return NextResponse.json({ encounterId, mode, status: "started" });
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const encounterId = searchParams.get("encounterId") ?? ENCOUNTER_ID;
  return NextResponse.json({
    encounterId,
    demoRunning: isDemoRunning(encounterId),
  });
}

export async function DELETE(request: Request) {
  const body = await request.json().catch(() => ({}));
  const encounterId = (body.encounterId as string) ?? ENCOUNTER_ID;
  stopDemo(encounterId);
  await resetEncounter(encounterId);
  return NextResponse.json({ encounterId, status: "reset" });
}
