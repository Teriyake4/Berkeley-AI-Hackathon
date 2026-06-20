import Anthropic from "@anthropic-ai/sdk";

const client = process.env.ANTHROPIC_API_KEY
  ? new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY })
  : null;

export function hasClaude(): boolean {
  return Boolean(client);
}

/**
 * Call Claude and parse the first JSON object or array from the response.
 * Retries once on rate-limit (429). Returns null on any unrecoverable error
 * so agents can fall through to heuristic fallbacks.
 */
export async function callClaudeJSON<T>(
  system: string,
  user: string,
  _agentName: string
): Promise<T | null> {
  if (!client) return null;

  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const response = await client.messages.create({
        model: "claude-sonnet-4-5",
        max_tokens: 2048,
        system:
          system +
          "\n\nIMPORTANT: Respond with ONLY the raw JSON — no markdown fences, no explanation.",
        messages: [{ role: "user", content: user }],
      });

      const raw =
        response.content[0]?.type === "text" ? response.content[0].text.trim() : "";

      // Strip markdown fences if Claude ignored the instruction
      const stripped = raw
        .replace(/^```(?:json)?\s*/i, "")
        .replace(/\s*```$/, "")
        .trim();

      // Match either top-level object or array
      const jsonMatch = stripped.match(/^(\{[\s\S]*\}|\[[\s\S]*\])$/);
      if (jsonMatch) return JSON.parse(jsonMatch[0]) as T;

      // Fallback: find the first JSON structure anywhere in the text
      const embedded = stripped.match(/\{[\s\S]*\}|\[[\s\S]*\]/);
      if (embedded) return JSON.parse(embedded[0]) as T;

      return null;
    } catch (err: unknown) {
      const status = (err as { status?: number }).status;
      if (status === 429 && attempt === 0) {
        await sleep(2000); // brief back-off on rate-limit
        continue;
      }
      return null;
    }
  }
  return null;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
