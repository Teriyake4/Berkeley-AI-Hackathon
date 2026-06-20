import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Returns the Deepgram API key for browser-side live transcription.
 * The browser connects directly to Deepgram WebSocket using this key.
 *
 * For production, replace with Deepgram temporary key creation:
 * https://developers.deepgram.com/reference/create-key
 */
export async function GET() {
  const key = process.env.DEEPGRAM_API_KEY;
  if (!key) {
    return NextResponse.json(
      { error: "Deepgram not configured" },
      { status: 503 }
    );
  }
  return NextResponse.json({ key });
}
