# Teammate 1 — Platform & Pipeline

**Branch:** `teammate-1/platform`  
**Mission:** Data in, events out, demo never breaks.

You own everything that ingests voice/transcript, runs the event bus, and streams events to the browser. You do **not** touch agent prompts, Claude logic, or dashboard styling.

---

## Your deliverables

- [ ] Demo Mode works 100% reliably (`POST /api/encounter`)
- [ ] SSE stream stable (`GET /api/events`)
- [ ] Live mic → transcript pipeline (Deepgram or Web Speech fallback)
- [ ] Redis connected for deploy (optional locally)
- [ ] Full demo runs without manual fixes

---

## Files you own

```
lib/bus.ts
lib/redis/**
lib/demo/injector.ts
lib/sse/hub.ts
lib/agents/runtime.ts
lib/agents/transcription.ts
app/api/**
instrumentation.ts
scripts/demo-scenario.json
scripts/run-local-bus.ts
components/LiveMic.tsx
.env.example          (REDIS_URL, DEEPGRAM_API_KEY sections only)
```

## Files you do NOT touch

```
components/**         (except LiveMic.tsx)
hooks/**
lib/agents/extraction.ts
lib/agents/timeline.ts
lib/agents/safety.ts
lib/agents/documentation.ts
lib/agents/research.ts
lib/agents/handoff.ts
lib/prompts/**
lib/claude.ts
lib/debounce.ts
```

---

## Env vars (your keys)

```bash
REDIS_URL=              # optional locally; needed for production
DEEPGRAM_API_KEY=       # for real Deepgram STT
```

Copy `.env.example` → `.env.local` and fill these.

---

## Build order

| # | Task | Done when |
|---|------|-----------|
| 1 | Confirm `npm run dev` + Demo button works | All panels update during replay |
| 2 | Harden `lib/demo/injector.ts` | Replay never crashes mid-scenario |
| 3 | Verify SSE in `app/api/events/route.ts` | Browser EventSource receives all events |
| 4 | Deepgram live streaming in `app/api/transcript/route.ts` + `LiveMic.tsx` | Live mode transcribes without Web Speech |
| 5 | Redis in `lib/bus.ts` + `lib/redis/client.ts` | Pub/sub works across restarts |
| 6 | Deploy (Vercel + Redis Cloud) | Remote demo URL works |

---

## Test in isolation (no Teammate 2 needed)

```bash
# Terminal 1
npm run dev

# Terminal 2 — trigger demo
curl -X POST http://localhost:3000/api/encounter \
  -H "Content-Type: application/json" \
  -d '{"mode":"demo"}'

# Terminal 3 — agent pipeline without UI
npm run local-bus
```

**Browser SSE test** (DevTools console):

```javascript
const es = new EventSource("/api/events");
es.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## API contract (you implement, Teammate 2 consumes)

### `GET /api/events`

Server-Sent Events stream. Each message:

```json
{ "channel": "timeline.updated", "payload": { ... } }
```

### `POST /api/encounter`

Body: `{ "mode": "demo" | "live", "encounterId"?: string }`  
Resets state. `demo` → replays `scripts/demo-scenario.json`.

### `POST /api/transcript`

Body: `{ "text": string, "speaker": "doctor"|"patient"|"unknown", "encounterId"?: string }`  
Publishes `transcript.segment`.

### `POST /api/handoff`

Body: `{ "encounterId"?: string }`  
Publishes `handoff.requested`. Do not change payload shape.

---

## Integration checkpoints

| When | You deliver |
|------|-------------|
| Hour 0 | Both devs: `npm install`, Demo runs once together |
| Hour 4 | Demo → SSE → browser receives events |
| Hour 8 | Live mic publishes segments (Deepgram or fallback) |
| Hour 12 | Deployed URL Teammate 2 can demo from |

**If demo breaks:** both stop. You fix bus/SSE first.

---

## Git rules

1. Work only on `teammate-1/platform`
2. Never edit Teammate 2's files
3. Before merging: `npm run build` passes
4. Merge to `main` every 3–4 hours; other person rebases

---

## Handoff to Teammate 2

Message when ready:

> "Bus is live — connect to `/api/events`, click Demo, you should see all event channels in the console."

---

## Reference

- [PARALLEL_BUILD.md](../PARALLEL_BUILD.md)
- [TEAMMATE_2.md](./TEAMMATE_2.md)
- [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)
- Shared contract: `lib/events.ts` — **sync before changing**
