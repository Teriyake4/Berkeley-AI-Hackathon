# Dev A — Platform & Multimodal Ingestion

**Branch:** `dev/a-platform`  
**Mission:** Get every signal into the bus reliably — voice, audio events, GPS, demo replay — and stream it to the browser.

You do **not** touch agent prompts, safety logic, dashboard styling, or Browserbase.

---

## Your deliverables

- [ ] Ambulance demo scenario replays end-to-end (`POST /api/encounter` demo mode)
- [ ] SSE stream stable (`GET /api/events`)
- [ ] Live mic → Deepgram (or fallback) with speaker labels: `paramedic` | `patient` | `bystander` | `unknown`
- [ ] Non-speech **audio events** published to timeline (silence, distress, equipment alarm)
- [ ] **GPS / telemetry** timestamps injected (scene arrival → patient contact → en route → hospital)
- [ ] Redis connected for deploy (optional locally)
- [ ] Full demo runs without manual fixes

---

## Files you own

```
lib/bus.ts
lib/redis/**
lib/demo/**
lib/sse/**
lib/agents/runtime.ts
lib/agents/transcription.ts
app/api/**                    (except handoff — Dev C owns route if split)
instrumentation.ts
scripts/demo-scenario.json    (rewrite for ambulance scenario)
scripts/run-local-bus.ts
components/LiveMic.tsx
backend/main.py               (ingestion routes only — coordinate)
backend/demo/injector.py
backend/sse/**
backend/redis_layer/**
.env.example                  (REDIS_URL, DEEPGRAM sections)
```

## Files you do NOT touch

```
components/**                 (except LiveMic.tsx)
hooks/**
lib/agents/extraction.ts
lib/agents/timeline.ts
lib/agents/safety.ts
lib/agents/documentation.ts
lib/agents/research.ts
lib/agents/handoff.ts
lib/prompts/**
lib/claude.ts
app/page.tsx
```

---

## Build order

| # | Task | Done when |
|---|------|-----------|
| 1 | Rewrite `scripts/demo-scenario.json` for **ambulance call** | Paramedic + patient dialogue; chest pain + warfarin beats; ends at hospital handoff trigger |
| 2 | Confirm demo + SSE | All event channels reach browser console |
| 3 | Deepgram live streaming | Live mode transcribes with speaker diarization |
| 4 | **Audio events layer** | Publish `audio.event` (or extend timeline) for: prolonged silence (>30s), raised voice/distress, repeated alarm tone |
| 5 | **GPS / telemetry** | Publish structured timestamps: `scene_arrival`, `patient_contact`, `depart_scene`, `hospital_arrival` (demo: scripted; live: mock or API stub) |
| 6 | Extend `lib/events.ts` **with team sync** | New payload types for `audio.event`, `telemetry.updated`, `vision.captured` stubs Dev C will fill |
| 7 | Redis + deploy | Remote demo URL works |

---

## Ambulance demo script (you maintain the JSON)

Replace ER doctor/patient with paramedic/patient. Minimum beats:

| Beat | Speaker | Line (example) | Expected ingestion |
|------|---------|------------------|-------------------|
| 1 | Paramedic | "Ma'am, I'm Alex with county EMS. What happened?" | Transcript + timeline start |
| 2 | Patient | "Chest pain for two hours, started gardening" | Segment published |
| 3 | Paramedic | "Any allergies? Medications?" | — |
| 4 | Patient | "Penicillin — rash. Lisinopril and warfarin." | Allergies + meds in transcript |
| 5 | *(optional)* | GPS: scene arrival timestamp | Telemetry on timeline |
| 6 | Paramedic | *(doesn't ask about aspirin for 3+ min while discussing vitals)* | Dev B flags missed follow-up — your timestamps must be accurate |
| 7 | Paramedic | "Generate handoff" / UI button | `handoff.requested` fires |

Coordinate beat timing with Dev B (safety timer) and Dev C (demo pitch).

---

## Non-speech audio events

Deepgram transcribes words; add a thin layer (Deepgram metadata, or simple heuristics on demo) for:

- `prolonged_silence` — no speech > N seconds during active encounter
- `distress` — elevated volume / agitation (flag only; no diagnosis)
- `equipment_alarm` — repeated tone pattern (demo: inject at fixed timestamp)

Publish so Dev B/C can show on timeline: *"Equipment alarm at 14:06"* alongside spoken entries.

```typescript
// Example envelope — finalize shape in lib/events.ts with team
{
  channel: "audio.event",
  payload: {
    encounterId,
    type: "prolonged_silence" | "distress" | "equipment_alarm",
    timestamp,
    detail?: string
  }
}
```

---

## GPS / telemetry

Not flashy, but handoff credibility depends on objective anchors.

Demo mode: inject fixed ISO timestamps in `demo-scenario.json`.  
Live mode: accept `POST /api/telemetry` with `{ event: "scene_arrival" | ... }` or stub from UI.

Dev C displays these on timeline; Dev B may use them in handoff agent context.

---

## Env vars

```bash
REDIS_URL=
DEEPGRAM_API_KEY=
```

---

## Test in isolation

```bash
npm run dev
curl -X POST http://localhost:3000/api/encounter \
  -H "Content-Type: application/json" \
  -d '{"mode":"demo"}'
```

Browser:

```javascript
const es = new EventSource("/api/events");
es.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## Handoff to Dev B & Dev C

> "Bus is live — ambulance demo replays on `/api/encounter`. Connect to `/api/events`. New channels: `audio.event`, `telemetry.updated`. Vision stub ready for Dev C."

---

## Reference

- [Claude_DEV_A.md](./Claude_DEV_A.md) — **agent team launch prompts**
- [CLAUDE.md](../CLAUDE.md) · [Project_Context.md](../Project_Context.md) · [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)
- [DEV_B.md](./DEV_B.md) · [DEV_C.md](./DEV_C.md)
- [PARALLEL_BUILD.md](../PARALLEL_BUILD.md)
- Shared contract: `lib/events.ts` — **sync before changing**
