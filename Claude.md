# Ambulance Copilot — Claude / AI Assistant Context

> Read this before making changes. Sync with teammates before editing `lib/events.ts` or `backend/events.py`.

## One-sentence pitch

Ambulance Copilot is a real-time AI teammate for paramedics that listens to scene dialogue, captures visual context (pills, wounds, bracelets), maintains a live patient picture, flags missed follow-ups and safety issues, researches drugs and injury protocols, and produces a hospital handoff report — so nothing gets lost between scene and ED.

## Why ambulance (not ER)

- **1-on-1 dialogue** — paramedic and patient (or bystander); easy to demo with two speakers.
- **Always a handoff** — every call ends with a structured report to the hospital; this is the demo money shot.
- **Practical constraints** — responder is multitasking; an agent that remembers what was said 5 minutes ago is immediately valuable.

## Core agents

| Agent | Job | Trigger | Output |
|-------|-----|---------|--------|
| **Transcription** | Live STT + speaker labels | Mic / demo injector | `transcript.segment` |
| **Extraction** | Pull entities from speech + vision | Debounced transcript; vision events | `facts.extracted` |
| **Timeline** | Chronological scene narrative | `facts.extracted`, telemetry, audio events | `timeline.updated` |
| **Safety** | Flag stated-fact concerns only | `facts.extracted`, vision, time-based checks | `safety.flagged` |
| **Documentation** | Live PCR / SOAP note | `facts.extracted` + timeline | `note.updated` |
| **Research** | Guidelines, interactions, injury protocols | New med/allergy/condition | `research.completed` |
| **Handoff** | Hospital transfer report | `handoff.requested` | `handoff.generated` |

## Safety agent rules (non-negotiable)

The safety agent may **only** flag **stated facts** — something said aloud, written on a bracelet/label, or identified via CV — cross-referenced against:

1. **Another stated fact** (internal contradiction or missed follow-up), or  
2. **An external reference** (drug interaction DB, clinical guideline via research agent).

**Never** flag something inferred purely from a demographic proxy (e.g. age alone).

### Demo trio (must all work in demo)

| Type | Example | Check |
|------|---------|-------|
| **Missed follow-up** | Chest pain mentioned at 0:00, not addressed for 3+ min | Transcript-internal timer |
| **Stated med + context** | Warfarin + chest pain | Transcript + Browserbase research |
| **CV med vs known meds** | Vial scanned: aspirin; patient on warfarin | Vision event + extraction cross-check |

Also remind paramedic if a **standard NREMT assessment question** was never asked (e.g. allergies, last oral intake).

## Allergies

**Always collect allergies.** Extraction must pull stated allergies; safety should flag if allergies are unknown after several minutes of assessment; handoff must include allergy status explicitly.

## Computer vision

- **Demo:** web app + laptop webcam — capture pills on scene, wounds, medical alert bracelets.
- **Pitch line:** *"In the field this would be chest- or helmet-mounted; we use a laptop cam for the hackathon."*
- CV output merges into `facts.extracted` and feeds safety cross-checks before medication administration.

## Multimodal inputs beyond speech

| Modality | Source | Timeline use |
|----------|--------|----------------|
| **Non-speech audio** | Deepgram / audio layer | Prolonged silence, raised voice/distress, monitor alarm tones |
| **GPS / telemetry** | Structured API or demo timestamps | Scene arrival → patient contact → en route → hospital arrival |

These anchor the handoff timeline objectively ("confirmed by GPS") vs verbal recall alone.

## Research agent

- Uses **Browserbase** to search clinical guidelines, drug interactions, injury protocols.
- Triggered when paramedic doesn't know something, or proactively when a high-risk med/condition appears.
- Findings appear in insights panel with citations.

## Dashboard

- **Left:** Live transcript (paramedic / patient / bystander)
- **Center:** Timeline (speech + audio events + GPS + vision)
- **Right:** AI insights (safety flags, NREMT reminders, research citations)
- **Bottom:** Live PCR/SOAP note
- **Modal:** Hospital handoff report (end demo here)
- **Banner:** *"Demo only — not for clinical use."*

## Repo layout

```
app/                    Next.js frontend
backend/                FastAPI agents + bus (Python)
lib/events.ts           Shared event contract (TypeScript)
backend/events.py       Mirror of event contract (Python)
components/             Dashboard panels
scripts/demo-scenario.json   Ambulance demo script
docs/DEV_A.md           Person 1 — platform & ingestion
docs/DEV_B.md           Person 2 — clinical brain & safety
docs/DEV_C.md           Person 3 — UI, research, CV, handoff
```

## Environment variables

See `.env.example`. Keys: `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`, `BROWSERBASE_*`, `REDIS_URL`.

## Coding conventions

- Structured JSON from Claude agents; no free-text-only outputs.
- Idempotent entity merge — don't drop previously extracted facts.
- No diagnosis in safety flags — use "consider …" / "verify …" language.
- Minimize scope; match existing patterns in `backend/` and `lib/`.
- Do not commit `.env` or secrets.

## Integration gates

| Hour | Pass criteria |
|------|---------------|
| 6 | Demo replay → SSE → browser logs all channels |
| 10 | Extraction + safety + timeline visible in UI |
| 14 | Research citations + handoff modal + one CV capture |
| 18 | Full ambulance demo script, 3 clean runs |

If the bus breaks, all devs stop feature work and fix ingestion first.
