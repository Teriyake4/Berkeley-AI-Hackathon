# Dev B — Clinical Brain & Safety

**Branch:** `dev/b-clinical`  
**Mission:** Extract every stated fact (especially **allergies**), build the timeline, and flag only defensible safety issues — missed follow-ups, NREMT gaps, med interactions, CV cross-checks.

You do **not** touch UI, Browserbase, webcam capture, or the event bus implementation.

---

## Your deliverables

- [ ] Extraction pulls **allergies, meds, conditions, symptoms** from ambulance dialogue
- [ ] Safety flags if **allergies never stated** after assessment window (~2 min demo)
- [ ] **Missed follow-up** flag: symptom stated early, not revisited in N minutes
- [ ] **NREMT reminder**: standard question never asked (allergies, last oral intake, etc.)
- [ ] **Stated med + context** flag triggers research hook (warfarin + chest pain)
- [ ] **CV med cross-check** when `vision.captured` arrives (aspirin vial vs patient on warfarin)
- [ ] Timeline merges speech facts + audio events + telemetry from Dev A
- [ ] Documentation agent maintains live PCR/SOAP note
- [ ] **Never** flag from demographic proxy alone (age without stated symptom chain)

---

## Files you own

```
lib/claude.ts
lib/debounce.ts
lib/prompts/extraction.ts
lib/prompts/timeline.ts
lib/prompts/safety.ts
lib/prompts/documentation.ts
lib/agents/extraction.ts
lib/agents/timeline.ts
lib/agents/safety.ts
lib/agents/documentation.ts
backend/agents/extraction.py
backend/agents/timeline.py
backend/agents/safety.py
backend/agents/documentation.py
backend/prompts/**
```

## Files you do NOT touch

```
components/**
hooks/**
app/page.tsx
lib/agents/research.ts
lib/agents/handoff.ts
lib/demo/**
app/api/**              (coordinate if adding agent hooks)
components/LiveMic.tsx
```

---

## Build order

| # | Task | Done when |
|---|------|-----------|
| 1 | Tune **extraction** for ambulance + **allergies first-class** | Demo beat 4 yields penicillin allergy, lisinopril, warfarin |
| 2 | **Allergy gap flag** | If no allergy stated by minute 2 → `safety.flagged` medium: "Allergies not documented" |
| 3 | **Missed follow-up timer** | Chest pain at 0:00, paramedic doesn't address for 3 min → flag + suggested reminder |
| 4 | **NREMT checklist** | Track which standard questions were asked; remind on missing (allergies, meds, last oral intake, etc.) |
| 5 | **Stated-fact interaction flags** | Warfarin + chest pain → high severity; rationale cites stated facts only |
| 6 | **Vision cross-check** | On `vision.captured` med ID → compare to `facts.extracted.medications`; flag before admin |
| 7 | Timeline agent consumes audio + telemetry | Timeline shows multimodal entries |
| 8 | Documentation agent | PCR/SOAP fills incrementally through demo |

---

## Safety agent — the demo trio

### 1. Missed follow-up (transcript-internal)

Track `symptoms[]` with first-mentioned timestamp. If paramedic dialogue doesn't reference that symptom (or related assessment) within **N minutes** (demo: 3 min), publish:

```json
{
  "concern": "Chest pain mentioned at 00:00 — not addressed in follow-up",
  "severity": "medium",
  "rationale": "Stated symptom with no documented reassessment or plan"
}
```

### 2. Stated condition/medication + external risk (research trigger)

When warfarin + chest pain both in `facts.extracted`, flag high and ensure research agent runs (Dev C implements Browserbase; you publish the fact that triggers it).

**Do not** flag "67yo → ACS" without a **stated** symptom chain.

### 3. CV medication cross-check

When Dev C publishes `vision.captured`:

```json
{ "identified": "aspirin 325mg", "source": "vial_label" }
```

Cross-check against extracted meds/conditions → flag interaction (aspirin + warfarin) **before administration**.

---

## NREMT standard questions (reminder list)

Maintain a checklist derived from primary assessment flow. Remind only when question was **never asked** and encounter is active:

- [ ] Allergies
- [ ] Medications
- [ ] Last oral intake
- [ ] Events leading to illness/injury (SAMPLE)
- [ ] Pertinent negatives for chief complaint

Publish as `safety.flagged` low/medium with `rationale: "NREMT: allergies not yet documented"`.

---

## Extraction priorities

1. **Allergies** — always in schema; never drop on merge  
2. Medications with dose if stated  
3. Chief complaint + symptom onset  
4. Conditions (HTN, anticoagulation, etc.)  
5. Vitals if spoken  

Prompt must use **ambulance terminology** (paramedic, scene, transport) not ER (attending, admit).

---

## Claude prompt rules

1. Structured JSON only  
2. Idempotent merge with current entities  
3. No diagnosis — "consider ACS workup", not "MI"  
4. Safety flags must cite **which stated fact** triggered them  

---

## Test in isolation

```bash
npm run local-bus
# or
cd backend && uvicorn main:app --reload
```

Expected at warfarin + chest pain beat:

```
[facts.extracted] allergies: penicillin; meds: lisinopril, warfarin
[safety.flagged] high — warfarin + chest pain (stated)
[timeline.updated] Anticoagulation on board | ...
```

Inject mock `vision.captured` to test cross-check without Dev C UI.

---

## Handoff to Dev C

> "Clinical brain live — `facts.extracted`, `safety.flagged`, `note.updated` fire on demo. Research should trigger on warfarin. Wire insights panel + handoff inputs."

---

## Reference

- [Claude.md](../Claude.md)
- [DEV_A.md](./DEV_A.md) · [DEV_C.md](./DEV_C.md)
- Shared contract: `lib/events.ts` — **sync before changing**
