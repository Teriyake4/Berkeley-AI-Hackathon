# Dev C — UI, Research, CV & Handoff

> **Use this file as your CLAUDE.md.**  
> **Project context:** [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)

**Branch:** `dev/c-product`  
**Mission:** Make judges say wow — dashboard, Browserbase research, webcam scene capture, and the **hospital handoff** money shot.

You do **not** touch the event bus, demo injector, or extraction/safety agent logic.

---

## Your deliverables

- [ ] Ambulance-themed dashboard — all panels update during demo
- [ ] **Research agent** (Browserbase): injury protocols, drug interactions, unknown meds
- [ ] **CV capture** — laptop webcam scans pills, wounds, medical bracelets; results feed extraction + safety
- [ ] UI note: *"Production: chest- or helmet-mounted camera"*
- [ ] Insights panel shows safety trio + NREMT reminders + research citations
- [ ] Live PCR/SOAP panel wired to `note.updated`
- [ ] **Handoff modal** — paramedic → hospital report (end demo here)
- [ ] Timeline shows GPS anchors + audio events + vision captures
- [ ] 3 clean demo rehearsals with talking points

---

## Files you own

```
app/page.tsx
app/layout.tsx
app/globals.css
components/**
  TranscriptPanel.tsx
  TimelinePanel.tsx
  InsightsPanel.tsx
  SoapPanel.tsx
  HandoffModal.tsx
  DisclaimerBanner.tsx
  VisionCapture.tsx          ← create
  TelemetryBar.tsx           ← create (optional)
hooks/useEncounterEvents.ts
lib/agents/research.ts
lib/agents/handoff.ts
lib/prompts/research.ts
lib/prompts/handoff.ts
app/api/handoff/route.ts
app/api/vision/route.ts      ← create (CV upload → Claude vision)
backend/agents/research.py
backend/agents/handoff.py
backend/prompts/handoff.py
backend/prompts/research.py
fixtures/full-encounter-state.json   (ambulance scenario)
```

## Files you do NOT touch

```
lib/bus.ts
lib/redis/**              (read-only OK)
lib/demo/**
lib/sse/**
lib/agents/extraction.ts
lib/agents/timeline.ts
lib/agents/safety.ts
lib/agents/documentation.ts
scripts/demo-scenario.json  (coordinate with Dev A)
components/LiveMic.tsx
```

---

## Build order

| # | Task | Done when |
|---|------|-----------|
| 1 | Rebrand UI: **Nos**, paramedic/patient speakers | Static fixture looks like field tool |
| 2 | Wire `useEncounterEvents` to SSE | Demo updates all panels |
| 3 | Timeline: render **GPS**, **audio events**, **vision** entries | Multimodal timeline visible |
| 4 | **Research agent** + Browserbase | Warfarin beat → citations in insights |
| 5 | **VisionCapture** component + API | Snap vial/bracelet → `vision.captured` → safety cross-check fires |
| 6 | Insights panel: safety severity colors + NREMT reminders + research | All three demo flags visible |
| 7 | **Handoff modal** — before (raw transcript) / after (structured hospital report) | Pitch ends here |
| 8 | Polish + demo script | 5-min flow rehearsed 3× |

---

## Research agent (Browserbase)

**Triggers:**

- New medication in `facts.extracted` not yet researched  
- New allergy or high-risk condition  
- Paramedic explicitly uncertain ("I don't know what this pill is") — extract from transcript  

**Queries (examples):**

- `warfarin aspirin interaction bleeding risk`
- `chest pain prehospital ACS guideline`
- `{unknown_pill_imprint} pill identifier`

Publish `research.completed` with 2–3 citations. Display under **References** in insights.

Paramedics can ask questions themselves in dialogue; research backs them up so the **handoff doc** includes everything the ED doctor needs.

---

## Computer vision (demo)

### UX

- Button: **Scan scene** → laptop webcam preview → capture frame  
- Use cases in demo: **pill vial**, **medical alert bracelet**, **visible wound** (optional)  
- Caption in UI: *"Demo uses laptop camera. In the field: chest-mounted body cam."*

### Flow

1. User captures image → `POST /api/vision`  
2. Claude vision (or heuristic fallback) → `{ identified, type: "medication"|"bracelet"|"wound", rawText? }`  
3. Publish `vision.captured` + merge into entities  
4. Dev B safety agent cross-checks med vs known list → insights flag  

**Demo beat:** Patient on warfarin → paramedic scans aspirin vial → **interaction flag before giving aspirin**.

---

## Handoff report (money shot)

Ambulance always hands off to hospital. Report must include:

- Patient summary + chief complaint  
- **Allergies** (prominent)  
- Timeline with **GPS-anchored** timestamps  
- Current medications (stated + vision-identified)  
- Outstanding questions  
- Recommended ED actions  
- Research citations for high-risk findings  

Flow:

1. Click **Generate Handoff Report**  
2. `POST /api/handoff` → `handoff.requested`  
3. Handoff agent → `handoff.generated`  
4. Modal: messy transcript | structured report — **stop demo here**

---

## Dashboard layout

```
┌──────────────────────────────────────────────────────────────┐
│ ⚠ Demo only — not for clinical use.     [Live | Demo] [📷 Scan] │
├──────────────┬──────────────────────────┬────────────────────┤
│  Transcript  │  Timeline (+ GPS/audio)  │  AI Insights       │
│  paramedic/  │                          │  flags · NREMT ·   │
│  patient     │                          │  research refs     │
├──────────────┴──────────────────────────┴────────────────────┤
│  Live PCR / SOAP note                                         │
├──────────────────────────────────────────────────────────────┤
│  Scene · En route · Hospital          [ Generate Handoff ]    │
└──────────────────────────────────────────────────────────────┘
```

---

## Panel → event mapping

| Panel | Events |
|-------|--------|
| Transcript | `transcript.segment` |
| Timeline | `timeline.updated`, `telemetry.updated`, `audio.event`, `vision.captured`, `safety.flagged` |
| Insights | `safety.flagged`, `research.completed`, NREMT reminders |
| SOAP | `note.updated` |
| Handoff modal | `handoff.generated` |

---

## Demo script (you lead pitch)

| Min | Action | Call out |
|-----|--------|----------|
| 0–1 | Problem: information lost between scene and ED | — |
| 1–2 | Start demo — paramedic assesses chest pain | Transcript + timeline |
| 2–3 | Allergies + warfarin extracted | Allergy line in note |
| 3–4 | Missed follow-up flag appears | "Agent remembered chest pain from 3 min ago" |
| 4 | Scan aspirin vial | CV + interaction flag |
| 5 | Research citations | Browserbase |
| 5 | **Handoff modal** | End — no architecture slide |

---

## Env vars

```bash
ANTHROPIC_API_KEY=
BROWSERBASE_API_KEY=
BROWSERBASE_PROJECT_ID=
ARIZE_SPACE_ID=          # optional
ARIZE_API_KEY=
```

---

## Test in isolation (hour 0–6)

Render from `fixtures/full-encounter-state.json` before SSE is ready.

Mock `vision.captured` dispatch in reducer to build Insights panel early.

---

## Reference

- [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md) — project context (read first)
- [DEV_A.md](./DEV_A.md) · [DEV_B.md](./DEV_B.md)
- [PARALLEL_BUILD.md](../PARALLEL_BUILD.md)
- Shared contract: `lib/events.ts` — **sync before changing**

---

# Claude Agent Team (parallel sub-agents)

**Prepend to every launch prompt:**

```
First read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md.
```

| Phase | Run in parallel | Wait for |
|-------|-----------------|----------|
| **0** | Agents 1 + 2 | — (fixtures only) |
| **1** | Agent 3 | Agent 1 layout exists |
| **2** | Agents 4 + 5 + 6 | Agent 3 SSE wired |
| **3** | Agent 7 | Agents 4–6 functional |
| **4** | Agent 8 | Full pipeline |

### Agent 1 — Dashboard Shell

**Launch prompt:**
```
You are Dashboard Shell agent on Nos (Dev C, Agent 1).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Rebrand UI to Nos; render fixtures/full-encounter-state.json statically.
```

### Agent 2 — Event Reducer & SSE Hook

**Launch prompt:**
```
You are Event Reducer agent on Nos (Dev C, Agent 2).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement hooks/useEncounterEvents.ts for all event channels including audio.event, telemetry.updated, vision.captured.
```

### Agent 3 — Multimodal Timeline UI

**Launch prompt:**
```
You are Multimodal Timeline UI agent on Nos (Dev C, Agent 3).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Extend TimelinePanel + TelemetryBar for GPS, audio, and vision entries.
```

### Agent 4 — Research + Browserbase

**Launch prompt:**
```
You are Research agent on Nos (Dev C, Agent 4).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement backend/agents/research.py with Browserbase when keyed, fallback otherwise.
```

### Agent 5 — Vision Capture

**Launch prompt:**
```
You are Vision Capture agent on Nos (Dev C, Agent 5).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Create VisionCapture.tsx, POST /api/vision, publish vision.captured.
```

### Agent 6 — Handoff Modal

**Launch prompt:**
```
You are Handoff agent on Nos (Dev C, Agent 6).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement handoff agent + HandoffModal before/after split. End demo on this screen.
```

### Agent 7 — Insights Panel Polish

**Launch prompt:**
```
You are Insights Polish agent on Nos (Dev C, Agent 7).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Polish InsightsPanel: safety colors, NREMT reminders, research citations.
```

### Agent 8 — Demo & Pitch Integration

**Launch prompt:**
```
You are Demo Integration agent on Nos (Dev C, Agent 8).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Verify full 5-min demo flow; polish ModeToggle. Fix only Dev C files.
```
