# Claude Agent Team — Dev B (Clinical Brain & Safety)

> **You are Dev B.** Run sub-agents **in parallel** where dependencies allow.

## Required reading (project background)

Read **before** launching any sub-agent:

1. **[Project_Context.md](../Project_Context.md)** — What Ambulance Copilot is, current scope, safety rules, demo trio, and integration gates.
2. **[ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)** — Hackathon goals, original demo structure, dashboard layout, sponsor tracks, and pitch (scope conflicts → follow Project_Context).

Then: [CLAUDE.md](../CLAUDE.md) · Human checklist: [DEV_B.md](./DEV_B.md)

**Branch:** `dev/b-clinical`  
**Mission:** Extract stated facts (especially allergies), build timeline, flag defensible safety issues, maintain live PCR/SOAP.

**Do not touch:** UI, Browserbase, webcam, event bus implementation, demo injector.

---

## How to run this team

| Phase | Run in parallel | Wait for |
|-------|-----------------|----------|
| **0** | Agent 0 only | Dev A Agent 0 (event contract) optional |
| **1** | Agent 1 only | — |
| **2** | Agents 2 + 3 + 4 | Agent 1 publishes `facts.extracted` |
| **3** | Agent 5 | Agents 2–4 stable |
| **4** | Agent 6 | All above |

**Safety rule (all agents):** Flag only **stated facts** (spoken, written, CV). Never flag from demographic proxy alone.

**Prepend to every launch prompt:**

```
First read Project_Context.md and ER_Copilot_Hackathon_Plan.md for project background and demo goals.
```

---

## Agent 0 — Shared LLM & Debounce *(run first)*

**Role:** Claude client + transcript debounce for extraction.

**Owns:**
```
backend/claude.py
backend/debounce.py
backend/llm_parse.py
lib/claude.ts
lib/debounce.ts
```

**Tasks:**
1. `callClaude(system, user, schema?)` → parsed JSON; NVIDIA NIM fallback if no Anthropic key.
2. Async debounce: ~4s buffer or 1.5s silence after punctuation → trigger extraction.
3. Subscribe to `transcript.segment`; maintain encounter buffer.

**Done when:** `npm run local-bus` or backend logs debounced extraction triggers on demo replay.

**Launch prompt:**
```
You are LLM & Debounce agent on Ambulance Copilot (Dev B, Agent 0).
Read docs/Claude_DEV_B.md. Implement/finish backend/claude.py, debounce.py, lib/claude.ts, lib/debounce.ts.
Debounce transcript segments before extraction. Structured JSON output. NIM fallback optional.
Do not touch UI or bus implementation.
```

---

## Agent 1 — Extraction *(after Agent 0)*

**Role:** Pull entities from ambulance dialogue; **allergies first-class**.

**Owns:**
```
backend/agents/extraction.py
backend/prompts/extraction.py
lib/agents/extraction.ts
lib/prompts/extraction.ts
```

**Tasks:**
1. Prompt tuned for paramedic/patient (not ER doctor).
2. Schema merge is idempotent — never drop stated allergies/meds.
3. Priorities: allergies → meds → chief complaint/symptoms → conditions → vitals.
4. Publish `facts.extracted` with full `MedicalEntities`.
5. Heuristic fallback when no API key (demo must still extract penicillin, warfarin, lisinopril, chest pain).

**Done when:** Demo beat 4 yields allergies + meds in `facts.extracted`.

**Launch prompt:**
```
You are Extraction agent on Ambulance Copilot (Dev B, Agent 1).
Read docs/Claude_DEV_B.md and docs/DEV_B.md. Tune extraction for ambulance dialogue.
Allergies are mandatory in schema and merge. Publish facts.extracted. Heuristic fallback for demo.
Files: backend/agents/extraction.py, backend/prompts/extraction.py (+ lib/ mirrors if used).
```

---

## Agent 2 — Safety *(parallel with 3 & 4 after Agent 1)*

**Role:** Demo trio + NREMT reminders.

**Owns:**
```
backend/agents/safety.py
backend/prompts/safety.py
lib/agents/safety.ts
lib/prompts/safety.ts
```

**Tasks:**

### Demo trio
1. **Missed follow-up:** chest pain stated early; paramedic doesn't revisit within 3 min → `safety.flagged` medium.
2. **Stated med + context:** warfarin + chest pain → high severity (cite stated facts in rationale).
3. **CV cross-check:** on `vision.captured` medication → compare to `facts.extracted.medications` → flag before admin (e.g. aspirin + warfarin).

### NREMT checklist
Remind if never asked: allergies, medications, last oral intake, SAMPLE events, pertinent negatives.

Publish `safety.flagged` with `{ concern, severity, rationale, flaggedAt }`. No diagnosis language.

**Also:** If allergies unknown after ~2 min active assessment → medium flag.

**Done when:** All three demo flags fire on scripted scenario (+ mock vision event test).

**Launch prompt:**
```
You are Safety agent on Ambulance Copilot (Dev B, Agent 2).
Read docs/Claude_DEV_B.md. Implement missed follow-up timer, NREMT question reminders, warfarin+chest pain flag, vision.captured med cross-check.
Only flag stated facts — never age-alone inference. backend/agents/safety.py + prompts/safety.py.
Include test instructions with mock vision.captured payload.
```

---

## Agent 3 — Timeline *(parallel with 2 & 4)*

**Role:** Chronological multimodal narrative.

**Owns:**
```
backend/agents/timeline.py
backend/prompts/timeline.py
lib/agents/timeline.ts
lib/prompts/timeline.ts
```

**Tasks:**
1. Subscribe: `facts.extracted`, `safety.flagged`, `audio.event`, `telemetry.updated`, `vision.captured`.
2. Merge into ordered `timeline.updated` entries with `source` metadata where useful.
3. Examples: "Scene arrival (GPS)", "Equipment alarm", "Penicillin allergy documented", "Warfarin on board".

**Done when:** Demo replay timeline includes speech + ≥1 telemetry + ≥1 audio event entry.

**Launch prompt:**
```
You are Timeline agent on Ambulance Copilot (Dev B, Agent 3).
Read docs/Claude_DEV_B.md. Consume facts.extracted, safety.flagged, audio.event, telemetry.updated, vision.captured.
Publish timeline.updated with merged chronological entries. backend/agents/timeline.py + prompts.
```

---

## Agent 4 — Documentation *(parallel with 2 & 3)*

**Role:** Live PCR / SOAP note.

**Owns:**
```
backend/agents/documentation.py
backend/prompts/documentation.py
lib/agents/documentation.py
lib/prompts/documentation.ts
```

**Tasks:**
1. Subscribe: `facts.extracted`, `timeline.updated`.
2. Incrementally fill S/O/A/P (or PCR sections) — not empty at handoff time.
3. **Allergies prominent** in Subjective/Assessment when known.
4. Publish `note.updated`.

**Done when:** SOAP fills through demo; allergy line visible before handoff beat.

**Launch prompt:**
```
You are Documentation agent on Ambulance Copilot (Dev B, Agent 4).
Read docs/Claude_DEV_B.md. Maintain live SOAP/PCR from facts + timeline. Allergies prominent when stated.
Publish note.updated incrementally. backend/agents/documentation.py + prompts/documentation.py.
```

---

## Agent 5 — Vision Consumer *(after Agent 2)*

**Role:** Wire safety cross-check to `vision.captured` (logic only; no camera UI).

**Owns:** safety.py extensions, extraction merge hook if vision merges entities

**Tasks:**
1. On `vision.captured`: merge identified med/bracelet text into encounter state if appropriate.
2. Trigger safety cross-check (Agent 2 rules) without duplicate flags.
3. Unit test with payload: `{ "identified": "aspirin 325mg", "captureType": "medication" }`.

**Done when:** Mock vision event → high interaction flag when patient on warfarin.

**Launch prompt:**
```
You are Vision Consumer agent on Ambulance Copilot (Dev B, Agent 5).
Read docs/Claude_DEV_B.md. Subscribe to vision.captured in safety (+ extraction if needed).
Cross-check scanned meds against facts.extracted. Demo: aspirin vial + warfarin patient → flag.
Minimal diff to safety.py and runtime subscriptions. No UI or /api/vision route.
```

---

## Agent 6 — Integration & Prompt QA *(run last)*

**Role:** Full clinical pipeline on demo replay.

**Owns:** `backend/agents/runtime.py` (agent subscriptions only)

**Tasks:**
1. Ensure all Dev B agents subscribe on startup.
2. Run demo or `local-bus`; verify channel order roughly: transcript → facts → timeline/safety/note.
3. Tune prompts until warfarin beat matches expected console output (see DEV_B.md).

**Done when:** Integration gate **Hour 10** clinical slice passes.

**Launch prompt:**
```
You are Integration agent on Ambulance Copilot (Dev B, Agent 6).
Read docs/Claude_DEV_B.md. Wire backend/agents/runtime.py subscriptions for extraction, timeline, safety, documentation, vision consumer.
Run demo replay; verify facts.extracted, safety.flagged (warfarin+chest pain), timeline.updated, note.updated.
Fix only Dev B files. Report expected vs actual per beat.
```

---

## Expected demo output (Agent 6 verifies)

```
[facts.extracted] allergies: penicillin; meds: lisinopril, warfarin; symptoms: chest pain
[safety.flagged] medium — chest pain not revisited within 3 min (after beat 6)
[safety.flagged] high — warfarin + chest pain (stated)
[safety.flagged] high — aspirin (vision) + warfarin (stated) [after mock vision]
[timeline.updated] multimodal entries including GPS + audio
[note.updated] SOAP with allergy line filled
```

---

## Handoff message

> Clinical brain live — `facts.extracted`, `safety.flagged`, `timeline.updated`, `note.updated` on demo. Research triggers on warfarin (Dev C). Wire insights + handoff inputs.

---

## File ownership summary

| Own | Never touch |
|-----|-------------|
| `backend/agents/extraction\|timeline\|safety\|documentation.py` | `backend/bus.py`, `backend/demo/**`, `components/**` |
| `backend/prompts/**`, `backend/claude.py`, `backend/debounce.py` | `backend/agents/research.py`, `handoff.py` |
| `lib/agents/extraction\|timeline\|safety\|documentation.ts` | `lib/bus.ts`, `hooks/**`, `app/page.tsx` |

**Env vars:** `ANTHROPIC_API_KEY`, `NVIDIA_API_KEY` (optional)
