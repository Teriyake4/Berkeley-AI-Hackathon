# Claude Agent Team — Dev A (Platform & Ingestion)

> **You are Dev A.** Run sub-agents **in parallel** where dependencies allow.

## Required reading (project background)

Read **before** launching any sub-agent:

1. **[Project_Context.md](../Project_Context.md)** — What Ambulance Copilot is, current scope, safety rules, demo trio, and integration gates.
2. **[ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)** — Hackathon goals, original demo structure, dashboard layout, sponsor tracks, and pitch (scope conflicts → follow Project_Context).

Then: [CLAUDE.md](../CLAUDE.md) · Human checklist: [DEV_A.md](./DEV_A.md)

**Branch:** `dev/a-platform`  
**Mission:** Every signal enters the bus reliably and streams to the browser.

**Do not touch:** agent prompts, safety logic, dashboard panels (except `LiveMic.tsx`), Browserbase, handoff UI.

---

## How to run this team

Launch **one Claude agent session per sub-agent** below. Use the **Launch prompt** verbatim (fill `{...}`).

**Prepend to every launch prompt:**

```
First read Project_Context.md and ER_Copilot_Hackathon_Plan.md for project background and demo goals.
```

| Phase | Run in parallel | Wait for |
|-------|-----------------|----------|
| **0** | Agent 0 only | — |
| **1** | Agents 1 + 2 | Agent 0 done |
| **2** | Agents 3 + 4 + 5 | Agent 1 done (bus + demo path) |
| **3** | Agent 6 | Agents 1–5 done |

**Merge rule:** Only Agent 0 may edit `lib/events.ts` / `backend/events.py`. Others consume the contract.

---

## Agent 0 — Contract Lead *(run first, solo)*

**Role:** Extend shared event types for multimodal ingestion.

**Owns:** `lib/events.ts`, `backend/events.py` (ingestion channels only)

**Tasks:**
1. Add `Speaker` values: `paramedic` | `patient` | `bystander` (keep legacy aliases if needed).
2. Add channels + payloads:
   - `audio.event` — `{ encounterId, type, timestamp, detail? }` where `type` ∈ `prolonged_silence` | `distress` | `equipment_alarm`
   - `telemetry.updated` — `{ encounterId, event, timestamp, label? }` where `event` ∈ `scene_arrival` | `patient_contact` | `depart_scene` | `hospital_arrival`
   - `vision.captured` — stub `{ encounterId, identified, captureType, timestamp, rawText? }` (Dev C fills consumer; define shape now)
3. Mirror types in Python dataclasses.
4. Do not break existing channel names.

**Done when:** TypeScript + Python compile; existing demo still publishes `transcript.segment`.

**Launch prompt:**
```
You are Contract Lead on Ambulance Copilot (Dev A, Agent 0).
Read Project_Context.md, ER_Copilot_Hackathon_Plan.md, and docs/Claude_DEV_A.md.
Extend lib/events.ts and backend/events.py with audio.event, telemetry.updated, and vision.captured.
Add paramedic/patient/bystander speakers. Mirror in Python. Minimal diff. Do not touch other files.
Verify types compile. Summarize payload shapes for other agents.
```

---

## Agent 1 — Bus & SSE *(parallel with Agent 2 after Agent 0)*

**Role:** Event bus + SSE fan-out to browser.

**Owns:**
```
backend/bus.py
backend/sse/hub.py
backend/redis_layer/**
lib/bus.ts
lib/redis/**
lib/sse/**
backend/routes/events.py
app/api/events/route.ts          (proxy or thin wrapper — match existing pattern)
instrumentation.ts
```

**Tasks:**
1. Ensure publish/subscribe works (Redis or in-memory fallback).
2. `GET /api/events` SSE streams `{ channel, payload }` envelopes for **all** channels including new ones.
3. Reconnect-safe: new clients receive subsequent events.
4. Document env: `REDIS_URL` optional locally.

**Done when:**
```bash
curl -N http://localhost:8000/api/events   # or :3000 via proxy
# shows events when demo runs
```

**Launch prompt:**
```
You are Bus & SSE agent on Ambulance Copilot (Dev A, Agent 1).
Read docs/Claude_DEV_A.md. Harden backend/bus.py, sse hub, and lib/bus.ts.
Ensure GET /api/events fans out all event channels. Redis optional with in-memory fallback.
Do not edit agent logic or UI. Test with existing demo if possible.
```

---

## Agent 2 — Demo Script & Injector *(parallel with Agent 1)*

**Role:** Ambulance demo scenario + reliable replay.

**Owns:**
```
scripts/demo-scenario.json
backend/demo/injector.py
backend/routes/encounter.py
app/api/encounter/route.ts
scripts/run-local-bus.ts
```

**Tasks:**
1. Rewrite scenario: paramedic + patient dialogue (chest pain, penicillin allergy, lisinopril, warfarin).
2. Accurate ISO timestamps for missed-follow-up window (chest pain at 0:00; paramedic skips revisit for 3+ min).
3. Inject telemetry beats: `scene_arrival`, `patient_contact`, optional `equipment_alarm` audio event.
4. `POST /api/encounter { "mode": "demo" }` resets state and replays without crashing.

**Done when:**
```bash
curl -X POST http://localhost:3000/api/encounter -H "Content-Type: application/json" -d '{"mode":"demo"}'
# replay completes; transcript + telemetry events published
```

**Launch prompt:**
```
You are Demo Script agent on Ambulance Copilot (Dev A, Agent 2).
Read docs/Claude_DEV_A.md and docs/DEV_A.md ambulance demo beats.
Rewrite scripts/demo-scenario.json and backend/demo/injector.py for paramedic/patient ambulance call.
Include telemetry.updated and at least one audio.event in the script.
POST /api/encounter demo mode must replay end-to-end. Do not touch extraction/safety/UI.
```

---

## Agent 3 — Deepgram & Live Mic *(after Agent 1)*

**Role:** Live speech → `transcript.segment`.

**Owns:**
```
backend/routes/deepgram.py
backend/routes/transcript.py
app/api/deepgram/route.ts
app/api/transcript/route.ts
lib/agents/transcription.ts
components/LiveMic.tsx
lib/agents/runtime.ts            (transcription wiring only)
```

**Tasks:**
1. Browser mic → API → Deepgram live (or Web Speech fallback if no key).
2. Speaker diarization mapped to `paramedic` | `patient` | `bystander` | `unknown`.
3. Each segment: `{ encounterId, text, speaker, timestamp }` published to bus.
4. Append segments to encounter buffer for Dev B debounce.

**Done when:** Live mode shows labeled transcript in SSE console logs.

**Launch prompt:**
```
You are Deepgram agent on Ambulance Copilot (Dev A, Agent 3).
Read docs/Claude_DEV_A.md. Implement live mic → transcript.segment with paramedic/patient speakers.
Own backend/routes/deepgram.py, transcript.py, components/LiveMic.tsx, lib/agents/transcription.ts.
Use Deepgram if DEEPGRAM_API_KEY set; graceful fallback otherwise. Publish to existing bus.
```

---

## Agent 4 — Audio Events *(parallel with 3 & 5)*

**Role:** Non-speech audio cues on the timeline.

**Owns:**
```
backend/agents/audio_events.py     (create)
backend/routes/audio.py            (create, optional)
# or hook in demo injector + live stub
```

**Tasks:**
1. Publish `audio.event` for: `prolonged_silence` (>30s no speech during active encounter), `distress` (demo: inject or heuristic), `equipment_alarm` (demo: fixed timestamp).
2. Demo path: injector already emits these (coordinate with Agent 2 schema).
3. Live path: stub detector or manual `POST /api/audio-event` for hackathon.

**Done when:** Demo replay emits ≥1 `audio.event`; SSE logs show type + timestamp.

**Launch prompt:**
```
You are Audio Events agent on Ambulance Copilot (Dev A, Agent 4).
Read docs/Claude_DEV_A.md. Implement audio.event publishing per lib/events.ts contract.
Demo: ensure injector fires equipment_alarm or prolonged_silence. Live: stub POST endpoint or silence timer.
Do not touch safety agents or UI. Minimal implementation.
```

---

## Agent 5 — GPS / Telemetry *(parallel with 3 & 4)*

**Role:** Objective timeline anchors.

**Owns:**
```
backend/routes/telemetry.py        (create)
app/api/telemetry/route.ts         (create, if proxied)
# demo beats in demo-scenario.json (coordinate Agent 2)
```

**Tasks:**
1. Publish `telemetry.updated` with `scene_arrival`, `patient_contact`, `depart_scene`, `hospital_arrival`.
2. Demo: scripted timestamps in scenario JSON.
3. Live: `POST /api/telemetry { "event": "scene_arrival" }` or UI stub for Dev C.

**Done when:** Demo replay emits ≥2 telemetry events with ISO timestamps.

**Launch prompt:**
```
You are Telemetry agent on Ambulance Copilot (Dev A, Agent 5).
Read docs/Claude_DEV_A.md. Implement telemetry.updated events and POST /api/telemetry stub.
Ensure demo scenario injects scene_arrival and patient_contact. Match lib/events.ts payloads.
Do not touch UI or clinical agents.
```

---

## Agent 6 — Integration & Deploy *(run last)*

**Role:** End-to-end smoke test + deploy readiness.

**Owns:** `.env.example` (REDIS_URL, DEEPGRAM sections), `docker-compose.yml` (if needed)

**Tasks:**
1. Full demo: encounter → SSE → all channels including audio + telemetry.
2. Fix cross-agent breakage only in Dev A owned files.
3. Document test commands in comment or DEV_A.md snippet.

**Done when:** Integration gate **Hour 6** passes (see Project_Context.md).

**Launch prompt:**
```
You are Integration agent on Ambulance Copilot (Dev A, Agent 6).
Read docs/Claude_DEV_A.md. Run demo end-to-end: POST /api/encounter demo, verify SSE receives transcript.segment, audio.event, telemetry.updated.
Fix only Dev A owned files. Update .env.example if new vars added. Report pass/fail per channel.
```

---

## Handoff message (post team run)

Post in team chat when Agents 1–6 complete:

> Bus live — ambulance demo on `POST /api/encounter`. SSE at `/api/events`. Channels: `transcript.segment`, `audio.event`, `telemetry.updated`, `vision.captured` (stub). Dev B/C can integrate.

---

## File ownership summary

| Own | Never touch |
|-----|-------------|
| `lib/bus.ts`, `lib/redis/**`, `lib/sse/**`, `lib/demo/**` | `lib/agents/extraction\|timeline\|safety\|documentation\|research\|handoff.ts` |
| `backend/bus.py`, `backend/demo/**`, `backend/sse/**`, ingestion routes | `backend/agents/extraction\|timeline\|safety\|...` (except audio_events.py) |
| `scripts/demo-scenario.json`, `LiveMic.tsx` | `components/**` except LiveMic, `app/page.tsx` |

**Env vars:** `REDIS_URL`, `DEEPGRAM_API_KEY`
