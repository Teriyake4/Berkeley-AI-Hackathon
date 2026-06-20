# Teammate 2 — Agents, UI & Demo

**Branch:** `teammate-2/product`  
**Mission:** Make judges say wow — agents, polish, pitch.

You own all Claude agents, prompts, dashboard UI, and the handoff money shot. You do **not** touch the event bus, API routes, or demo injector.

---

## Your deliverables

- [ ] All 4 dashboard panels update smoothly during Demo
- [ ] Warfarin safety flag appears mid-demo (high severity)
- [ ] Research citations appear in insights panel
- [ ] SOAP note fills in live
- [ ] Handoff modal (before/after) is pitch-ready
- [ ] Claude prompts tuned on scripted scenario
- [ ] 3 clean demo rehearsals with talking points

---

## Files you own

```
components/**         (except LiveMic.tsx — Teammate 1 owns that)
hooks/useEncounterEvents.ts
app/page.tsx
app/layout.tsx
app/globals.css
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

## Files you do NOT touch

```
lib/bus.ts
lib/redis/**
lib/demo/**
lib/sse/**
app/api/**
instrumentation.ts
scripts/demo-scenario.json   (coordinate with Teammate 1 if changing beats)
components/LiveMic.tsx
```

---

## Env vars (your keys)

```bash
ANTHROPIC_API_KEY=          # Claude for all agents
BROWSERBASE_API_KEY=        # research agent
BROWSERBASE_PROJECT_ID=
ARIZE_SPACE_ID=             # optional — observability
ARIZE_API_KEY=
```

Copy `.env.example` → `.env.local` and fill these.

---

## Build order

| # | Task | Done when |
|---|------|-----------|
| 1 | Dashboard renders from fixture | `fixtures/full-encounter-state.json` looks good static |
| 2 | Wire `hooks/useEncounterEvents.ts` to SSE | Demo button updates all panels |
| 3 | Tune extraction/safety prompts | Warfarin → high safety flag by beat 6 |
| 4 | Research agent + Browserbase | Citations in insights panel |
| 5 | Handoff modal polish | Before/after split is the final demo screen |
| 6 | UI polish | Animations, severity colors, auto-scroll transcript |
| 7 | Demo script + pitch | 5-min flow rehearsed 3x |

---

## Test in isolation (before SSE is ready)

**Static UI from fixture** — temporarily in `app/page.tsx`:

```typescript
import fixture from "@/fixtures/full-encounter-state.json";
// render panels from fixture data
```

**Agent pipeline without UI:**

```bash
npm run local-bus
```

Expected at warfarin beat:

```
[facts] lisinopril, warfarin
[safety] high Warfarin + chest pain...
[research] warfarin drug interactions...
```

Compare against `fixtures/full-encounter-state.json`.

---

## Demo script (memorize beats)

| Beat | Line | Expected UI |
|------|------|-------------|
| 1 | "chest pain for two hours" | Transcript + timeline entry |
| 2 | "67... hypertension... lisinopril" | Entities extracted |
| 3 | "warfarin for heart valve" | **Safety flag (high)** + research citations |
| 4 | "short of breath... left arm" | SOAP updates, missing-info checklist |
| 5 | "ECG and troponin..." | Plan section fills |
| 6 | Click **Generate Handoff Report** | **Money shot modal — end here** |

---

## Panel → event mapping

| Panel | Events to handle |
|-------|------------------|
| Transcript | `transcript.segment` |
| Timeline | `timeline.updated`, `safety.flagged` |
| Insights | `safety.flagged`, `research.completed`, missing-info derived from entities |
| SOAP | `note.updated` |
| Handoff modal | `handoff.generated` |

All handled in `hooks/useEncounterEvents.ts` — this is your main integration file.

---

## Prompt tuning priorities

1. **Extraction** — must pull warfarin, lisinopril, age 67, chest pain before beat 6 ends
2. **Safety** — warfarin + chest pain = `high`; age + arm radiation = `medium`
3. **Documentation** — SOAP fills incrementally, not empty at handoff time
4. **Handoff** — structured report with outstanding questions (INR?) and recommended actions

Without `ANTHROPIC_API_KEY`, heuristics in `lib/prompts/` still work — but tune with Claude for the real demo.

---

## Integration checkpoints

| When | You deliver |
|------|-------------|
| Hour 0 | Static dashboard from fixture looks professional |
| Hour 4 | All panels wired to SSE |
| Hour 8 | Safety + research visible during demo |
| Hour 12 | Handoff modal + 3 rehearsal runs |

---

## Git rules

1. Work only on `teammate-2/product`
2. Never edit Teammate 1's files
3. Before merging: `npm run build` passes
4. Merge to `main` every 3–4 hours; rebase onto latest

---

## Pitch ownership (you lead)

- Minute 1–2: problem + start demo
- Minute 3: point at each panel updating
- Minute 4: handoff modal (**stop here**)
- Minute 5: 30-sec architecture (Teammate 1 supports on diagram)

---

## Reference

- [PARALLEL_BUILD.md](../PARALLEL_BUILD.md)
- [TEAMMATE_1.md](./TEAMMATE_1.md)
- [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)
- Shared contract: `lib/events.ts` — **sync before changing**
