# Claude Agent Team — Dev C (UI, Research, CV & Handoff)

> **You are Dev C.** Run sub-agents **in parallel** where dependencies allow.

## Required reading (project background)

Read **before** launching any sub-agent:

1. **[Project_Context.md](../Project_Context.md)** — What Ambulance Copilot is, current scope, safety rules, demo trio, and integration gates.
2. **[ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)** — Hackathon goals, original demo structure, dashboard layout, sponsor tracks, and pitch (scope conflicts → follow Project_Context).

Then: [CLAUDE.md](../CLAUDE.md) · Human checklist: [DEV_C.md](./DEV_C.md)

**Branch:** `dev/c-product`  
**Mission:** Dashboard, Browserbase research, webcam CV, hospital handoff money shot.

**Do not touch:** event bus, demo injector, extraction/safety agent logic, `LiveMic.tsx`.

---

## How to run this team

| Phase | Run in parallel | Wait for |
|-------|-----------------|----------|
| **0** | Agents 1 + 2 | — (fixtures only; no backend required) |
| **1** | Agent 3 | Agent 1 layout exists |
| **2** | Agents 4 + 5 + 6 | Agent 3 SSE wired; Dev A demo optional |
| **3** | Agent 7 | Agents 4–6 functional |
| **4** | Agent 8 | Full pipeline |

**Start early:** Agents 1–2 need only `fixtures/full-encounter-state.json` — no waiting on Dev A/B.

**Prepend to every launch prompt:**

```
First read Project_Context.md and ER_Copilot_Hackathon_Plan.md for project background and demo goals.
```

---

## Agent 1 — Dashboard Shell *(parallel with Agent 2)*

**Role:** Ambulance-themed layout + static fixture render.

**Owns:**
```
app/page.tsx
app/layout.tsx
app/globals.css
components/Dashboard.tsx
components/TranscriptPanel.tsx
components/TimelinePanel.tsx
components/InsightsPanel.tsx
components/SoapPanel.tsx
components/DisclaimerBanner.tsx
fixtures/full-encounter-state.json   (ambulance scenario)
```

**Tasks:**
1. Rebrand **Ambulance Copilot** (not ER Copilot).
2. Speakers: paramedic / patient / bystander in transcript panel.
3. Four-panel layout + disclaimer banner (see DEV_C.md diagram).
4. Render from fixture before SSE exists.

**Done when:** `npm run dev` shows polished static dashboard from fixture JSON.

**Launch prompt:**
```
You are Dashboard Shell agent on Ambulance Copilot (Dev C, Agent 1).
Read docs/Claude_DEV_C.md and docs/DEV_C.md layout diagram.
Rebrand UI to Ambulance Copilot. Build/update panel components; render fixtures/full-encounter-state.json statically.
Update fixture for ambulance scenario (allergies, warfarin, chest pain). Do not touch backend agents or bus.
```

---

## Agent 2 — Event Reducer & SSE Hook *(parallel with Agent 1)*

**Role:** Client state from SSE events.

**Owns:**
```
hooks/useEncounterEvents.ts
components/ModeToggle.tsx          (create if missing)
```

**Tasks:**
1. Reducer handles all channels: `transcript.segment`, `facts.extracted`, `timeline.updated`, `safety.flagged`, `note.updated`, `research.completed`, `handoff.generated`, `audio.event`, `telemetry.updated`, `vision.captured`.
2. `EventSource("/api/events")` with reconnect.
3. `USE_MOCK` or fixture replay mode for hour 0–6 dev.
4. Map events → panel props (see DEV_C.md table).

**Done when:** Demo button updates all panels when SSE live.

**Launch prompt:**
```
You are Event Reducer agent on Ambulance Copilot (Dev C, Agent 2).
Read docs/Claude_DEV_C.md. Implement hooks/useEncounterEvents.ts reducer for all event channels including audio.event, telemetry.updated, vision.captured.
Support mock/fixture replay mode. Wire to panel state. Do not implement research/handoff agents yet.
```

---

## Agent 3 — Multimodal Timeline UI *(after Agents 1–2)*

**Role:** Timeline renders GPS, audio, vision — not just speech.

**Owns:**
```
components/TimelinePanel.tsx       (extend)
components/TelemetryBar.tsx      (create)
```

**Tasks:**
1. Distinct styling for telemetry (GPS pin), audio events (alarm icon), vision (camera), safety flags.
2. Optional header bar: Scene · En route · Hospital from latest telemetry.
3. Auto-scroll / fade-in polish.

**Done when:** Mock dispatch of telemetry + audio + vision updates timeline visually.

**Launch prompt:**
```
You are Multimodal Timeline UI agent on Ambulance Copilot (Dev C, Agent 3).
Read docs/Claude_DEV_C.md. Extend TimelinePanel + create TelemetryBar for telemetry.updated, audio.event, vision.captured entries.
Distinct icons/colors per source. Use mock events in reducer if SSE unavailable.
```

---

## Agent 4 — Research + Browserbase *(parallel with 5 & 6)*

**Role:** External guidelines & drug interaction lookup.

**Owns:**
```
backend/agents/research.py
backend/prompts/research.py
lib/agents/research.ts
lib/prompts/research.ts
```

**Tasks:**
1. Trigger on new med/allergy in `facts.extracted` (dedupe per encounter).
2. Browserbase search when `BROWSERBASE_API_KEY` set; heuristic/PubMed fallback otherwise.
3. Queries: warfarin interactions, chest pain prehospital guideline, unknown pill.
4. Publish `research.completed` with 2–3 citations.
5. Insights panel section "References" (coordinate Agent 2 reducer).

**Done when:** Warfarin demo beat → citations appear in insights.

**Launch prompt:**
```
You are Research agent on Ambulance Copilot (Dev C, Agent 4).
Read docs/Claude_DEV_C.md. Implement backend/agents/research.py with Browserbase when keyed, fallback otherwise.
Trigger on new medications/allergies in facts.extracted. Publish research.completed with citations.
Ensure InsightsPanel displays references via useEncounterEvents.
```

---

## Agent 5 — Vision Capture *(parallel with 4 & 6)*

**Role:** Laptop webcam → `vision.captured` → safety cross-check (Dev B).

**Owns:**
```
components/VisionCapture.tsx       (create)
app/api/vision/route.ts            (create)
backend/routes/vision.py           (create)
```

**Tasks:**
1. UI: **Scan scene** button → webcam preview → capture frame.
2. Caption: *"Demo uses laptop camera. In the field: chest-mounted body cam."*
3. Claude vision (or heuristic) → `{ identified, captureType, rawText? }`.
4. Publish `vision.captured` on bus.
5. Demo beat: scan aspirin vial → Dev B flags interaction.

**Done when:** Capture → SSE logs `vision.captured` → insights shows safety flag.

**Launch prompt:**
```
You are Vision Capture agent on Ambulance Copilot (Dev C, Agent 5).
Read docs/Claude_DEV_C.md. Create VisionCapture.tsx, POST /api/vision, backend vision route.
Claude vision or fallback to identify pill vial / medical bracelet. Publish vision.captured per lib/events.ts.
Add demo caption about chest-mounted camera in production. Do not implement safety logic (Dev B).
```

---

## Agent 6 — Handoff Modal *(parallel with 4 & 5)*

**Role:** Hospital transfer report — **demo money shot**.

**Owns:**
```
backend/agents/handoff.py
backend/prompts/handoff.py
backend/routes/handoff.py
lib/agents/handoff.ts
lib/prompts/handoff.ts
app/api/handoff/route.ts
components/HandoffModal.tsx
```

**Tasks:**
1. Button → `POST /api/handoff` → `handoff.requested` → agent → `handoff.generated`.
2. Report includes: summary, **allergies**, GPS-anchored timeline, meds (spoken + vision), outstanding questions, ED actions, research citations.
3. Modal: split view raw transcript | structured report.
4. **End demo on this screen.**

**Done when:** Handoff button produces full report from demo state.

**Launch prompt:**
```
You are Handoff agent on Ambulance Copilot (Dev C, Agent 6).
Read docs/Claude_DEV_C.md. Implement handoff agent + HandoffModal before/after split.
Report must highlight allergies and include timeline + citations. POST /api/handoff flow end-to-end.
Polish modal as final demo screen.
```

---

## Agent 7 — Insights Panel Polish *(after 4–6)*

**Role:** Safety trio + NREMT + research in one panel.

**Owns:**
```
components/InsightsPanel.tsx
```

**Tasks:**
1. Severity colors: high red, medium amber, low blue.
2. Sections: Active flags · NREMT reminders · References.
3. Empty states + loading skeletons.

**Done when:** All three demo safety flags + citations visible during replay.

**Launch prompt:**
```
You are Insights Polish agent on Ambulance Copilot (Dev C, Agent 7).
Read docs/Claude_DEV_C.md. Polish InsightsPanel: safety severity colors, NREMT reminder display, research citations section.
Consume safety.flagged and research.completed from reducer. Match Ambulance Copilot visual style.
```

---

## Agent 8 — Demo & Pitch Integration *(run last)*

**Role:** Rehearsal-ready 5-minute flow.

**Owns:** demo talking points in `docs/DEV_C.md` (optional update), final UI polish pass

**Tasks:**
1. Live | Demo toggle works.
2. Full run: demo → flags → scan vial → research → handoff modal.
3. 3 clean rehearsals checklist.
4. Fix only Dev C files; file issues for Dev A/B blockers.

**Done when:** Integration gates **Hour 14** and **Hour 18** pass.

**Launch prompt:**
```
You are Demo Integration agent on Ambulance Copilot (Dev C, Agent 8).
Read docs/Claude_DEV_C.md demo script table. Verify full 5-min flow: demo replay, missed follow-up flag, vision scan, research citations, handoff modal.
Polish transitions and ModeToggle. Report blockers by dev. Fix only Dev C owned files.
```

---

## Demo script (Agent 8 validates)

| Min | Action | Call out |
|-----|--------|----------|
| 0–1 | Problem: info lost scene → ED | — |
| 1–2 | Start demo — chest pain assessment | Transcript + timeline |
| 2–3 | Allergies + warfarin extracted | Allergy in SOAP |
| 3–4 | Missed follow-up flag | "Agent remembered chest pain" |
| 4 | Scan aspirin vial | CV + interaction flag |
| 5 | Research citations | Browserbase |
| 5 | **Handoff modal** | Stop — no arch slide |

---

## Handoff message

> Product ready — dashboard wired, research + vision + handoff on demo. End pitch on handoff modal.

---

## File ownership summary

| Own | Never touch |
|-----|-------------|
| `app/page.tsx`, `components/**` (except LiveMic) | `lib/bus.ts`, `backend/demo/**`, `backend/bus.py` |
| `hooks/useEncounterEvents.ts` | `backend/agents/extraction\|timeline\|safety\|documentation.py` |
| `backend/agents/research.py`, `handoff.py`, vision routes | `scripts/demo-scenario.json` (coordinate Dev A) |

**Env vars:** `ANTHROPIC_API_KEY`, `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID`
