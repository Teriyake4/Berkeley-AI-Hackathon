# ER Copilot — AI Clinical Operations Assistant
## UC Berkeley AI Hackathon Project Plan

> **Ready to build?** → [PARALLEL_BUILD.md](./PARALLEL_BUILD.md) · [Dev A](./docs/DEV_A.md) · [Dev B](./docs/DEV_B.md) · [Dev C](./docs/DEV_C.md)

## One-Sentence Pitch

ER Copilot is a real-time AI teammate for clinicians that listens to patient conversations, maintains a live understanding of the case, generates documentation automatically, flags potential concerns, and produces perfect handoff reports during shift changes.

---

# Why This Can Win

Most hackathon healthcare projects are:
- Chatbots
- Symptom checkers
- Medical search engines

ER Copilot instead:

- Takes action
- Operates continuously
- Demonstrates multiple collaborating agents
- Uses real-time voice
- Solves a universally understandable problem
- Has obvious business value

Judges should immediately understand:

"Doctors spend too much time documenting. This reduces paperwork and prevents information loss."

---

# Full Product Scope

Ship all of this. No reduced scope — build the complete product.

## Six Agents (all required)

| Agent | Job | Trigger | Output |
|-------|-----|---------|--------|
| **Transcription** | Live speech-to-text | Microphone / demo injector | `transcript.segment` |
| **Extraction** | Pull medical entities from conversation | Debounced transcript buffer | `facts.extracted` |
| **Timeline** | Build chronological case narrative | `facts.extracted` | `timeline.updated` |
| **Safety** | Flag clinical concerns | `facts.extracted` | `safety.flagged` |
| **Documentation** | Maintain live SOAP note | `facts.extracted` + `timeline.updated` | `note.updated` |
| **Research** | Look up guidelines & drug interactions | New medication/allergy detected | `research.completed` |
| **Handoff** | Generate shift-change report | `handoff.requested` (UI button) | `handoff.generated` |

## Dashboard (all panels required)

- **Left:** Live transcript with speaker labels
- **Center:** Patient timeline (auto-updating)
- **Right:** AI insights (concerns, missing info, follow-up questions, research citations)
- **Bottom:** Live SOAP note
- **Modal:** Handoff report (before/after money shot)

## Infrastructure (all required)

- Deepgram streaming STT + speaker diarization
- Claude Sonnet for all LLM reasoning
- Redis pub/sub event bus + encounter state persistence
- Browserbase for research agent web retrieval
- Arize for latency and extraction quality monitoring
- Demo Mode fallback (scripted event injection)
- Disclaimer banner: *"Demo only — not for clinical use."*

## Post-Hackathon (not in scope)

- Multi-patient dashboard
- Patient memory across visits
- Voice Q&A mode ("What medications is this patient taking?")
- Differential diagnosis generator
- Risk severity timeline chart

---

# Core Demo

## Scripted Scenario

Use this exact script for demo prep, prompt tuning, and Demo Mode. Every beat maps to a visible UI update.

### Beat 1 — Chief complaint (0:00)

**Doctor:** "Good morning. I'm Dr. Chen. What brings you in today?"

**Patient:** "I've had chest pain for about two hours. It started suddenly while I was gardening."

*Expected:* Transcript appears. Timeline: "Patient reports acute chest pain, 2hr duration, exertional onset."

### Beat 2 — Demographics & history (0:30)

**Doctor:** "Can you tell me your age and any medical history?"

**Patient:** "I'm 67. I have hypertension — been on lisinopril for years."

*Expected:* Extraction pulls age, HTN, lisinopril. Timeline updates.

### Beat 3 — High-alert medication (1:00)

**Doctor:** "Any other medications? Blood thinners?"

**Patient:** "Yes, I take warfarin for a heart valve replacement."

*Expected:* Safety agent flags: **Warfarin + chest pain → bleeding/anticoagulation risk, consider ACS workup.** Research agent returns warfarin contraindication references via Browserbase.

### Beat 4 — Missing information (1:30)

**Doctor:** "Any shortness of breath, nausea, or pain radiating to your arm or jaw?"

**Patient:** "A little short of breath, but no nausea. The pain does go to my left arm."

*Expected:* Insights panel updates missing-info checklist. SOAP note O-section fills in.

### Beat 5 — Plan & handoff (2:00)

**Doctor:** "We'll get an ECG and troponin right away. I'm going to start aspirin and consult cardiology."

*Press "Generate Handoff Report"*

*Expected:* Structured handoff with patient summary, timeline, medications, outstanding questions, recommended next actions. **This is the final screen judges see.**

---

# The Money Shot

At the end of the demo, split-screen or tab switch:

## Before

Messy raw transcript.

## After

Perfect shift handoff report:

- Patient summary
- Timeline
- Current medications
- Outstanding questions
- Recommended next actions

End on this screen. Do not end on an architecture slide.

---

# Tracks To Target

## Anthropic (primary)

Use Claude Sonnet for:

- Structured entity extraction (JSON schema output)
- Timeline narrative generation
- Safety concern analysis
- SOAP note sections
- Handoff report generation

Every agent in the Claude path logs prompts and outputs to Arize.

---

## Deepgram (primary)

- Streaming Speech-to-Text (live demo)
- Speaker diarization (Doctor vs Patient labels)

Voice is central. Live mic is the wow moment. Demo Mode uses the same pipeline with pre-recorded audio — still processed through Deepgram when possible, otherwise inject `transcript.segment` events directly.

---

## Browserbase

Research agent only. Triggered when a **new** medication or allergy entity appears in `facts.extracted`.

Tasks:

- Drug interaction lookup (e.g., warfarin + aspirin)
- Guideline retrieval (chest pain / ACS pathway)
- Return 2–3 citations displayed in the insights panel

Do not use Browserbase for general web search — scoped queries only.

---

## Redis

| Use | How |
|-----|-----|
| Event bus | Pub/sub channels per event type |
| Encounter state | `encounter:{id}:transcript`, `:facts`, `:timeline`, `:soap` |
| Agent debounce | Buffer transcript chunks before extraction trigger |
| Research cache | Cache Browserbase results by drug name (avoid repeat lookups) |

No vector retrieval in v1 — plain key-value is enough.

---

## Band (multi-agent track)

**We are not using the Band SDK.** Satisfy this track by demonstrating six independent agents coordinated through Redis pub/sub. Pitch line: *"A collaborative AI workforce — each agent is a specialist that reacts to clinical events in real time."*

---

## Arize

Instrument from hour 6 onward:

- End-to-end latency (transcript → timeline update)
- Extraction accuracy (spot-check against scripted scenario)
- Claude token usage per agent

Show one Arize dashboard screenshot during the 30-second architecture beat — only if traces are live.

---

# Design Pattern: Event-Driven Architecture (Pub/Sub)

## Why This Pattern

Three vibe coders building six agents in parallel will collide fast without a shared contract. **Event-Driven Architecture** gives everyone the same rule:

> Agents don't call each other directly. They publish events. Other agents subscribe and react.

This matches the product (clinical events happen continuously), the stack (Redis pub/sub + WebSocket fan-out), and the demo narrative ("collaborative AI workforce reacting in real time").

---

## Core Idea

```
Deepgram / Demo Mode → transcript.segment
              ↓
     [Event Bus — Redis or asyncio in-memory]
         ↙    ↓    ↓    ↘
   extraction  timeline  safety  documentation
         ↓         ↓        ↓          ↓
    facts.extracted  timeline.updated  safety.flagged  note.updated
         ↓
    research (on new med/allergy) → research.completed
              ↓
         [SSE /api/events → Frontend]
              ↓
    handoff.requested → handoff.generated
```

Every state change is an **event** with a typed payload. Agents are **dumb subscribers** — easy to vibe-code in isolation because the only contract is the event schema.

---

## Event Schema

Defined in `backend/events.py` (Python dataclasses). Never rename fields; add new event types instead.

| Event | Publisher | Payload |
|-------|-----------|---------|
| `transcript.segment` | Voice / Demo Mode | `{ text, speaker, timestamp, encounterId }` |
| `facts.extracted` | Extraction agent | `{ entities: { medications, conditions, allergies, vitals, symptoms }, encounterId }` |
| `timeline.updated` | Timeline agent | `{ events: TimelineEntry[], encounterId }` |
| `safety.flagged` | Safety agent | `{ concern, severity: 'low'\|'medium'\|'high', rationale, encounterId }` |
| `note.updated` | Documentation agent | `{ soap: { subjective, objective, assessment, plan }, encounterId }` |
| `research.completed` | Research agent | `{ query, findings: string, citations: Citation[], encounterId }` |
| `handoff.requested` | Frontend | `{ encounterId }` |
| `handoff.generated` | Handoff agent | `{ report: HandoffReport, encounterId }` |

---

## Latency & Debouncing

Raw transcript fires fast. Claude calls do not run on every chunk.

| Agent | Trigger rule |
|-------|-------------|
| Extraction | Every 4 seconds of new transcript **or** 1.5s silence (sentence boundary) |
| Timeline | On every `facts.extracted` |
| Safety | On every `facts.extracted` |
| Documentation | Every 8 seconds **or** on `timeline.updated` |
| Research | Only when a **new** medication or allergy appears (dedupe via Redis set) |
| Handoff | On demand only |

Buffer transcript in Redis (`encounter:{id}:buffer`). Extraction agent reads buffer, not individual segments.

---

## Three-Dev Split

Two agents per dev. Clean ownership, no bottleneck.

| Dev | Owns | Subscribes To | Publishes |
|-----|------|---------------|-----------|
| **Dev A — Voice & Bus** | Deepgram, WebSocket server, Redis setup, Demo Mode injector, Transcription | — | `transcript.segment` |
| **Dev B — Clinical Brain** | Extraction, Timeline, Safety agents (Claude prompts + handlers) | `transcript.segment` (via buffer), internal | `facts.extracted`, `timeline.updated`, `safety.flagged` |
| **Dev C — Output & UI** | Documentation, Research (Browserbase), Handoff agents + full Next.js dashboard | `facts.extracted`, `timeline.updated`, `safety.flagged`, `research.completed`, `note.updated`, `handoff.generated` | `handoff.requested`, `note.updated`, `research.completed`, `handoff.generated` |

Integration happens through the event bus, not function imports.

---

## Rules for Vibe Coding

1. **No direct agent-to-agent imports.** Subscribe to events; never import another agent's module.
2. **One shared `backend/events.py`.** Everyone imports from it. Never rename fields.
3. **Idempotent handlers.** Events may replay; agents upsert state, not append blindly.
4. **Redis = source of truth.** Pub/sub for live updates; Redis keys for encounter state so refresh doesn't lose the case. In-memory fallback for offline dev.
5. **Frontend is read-only + triggers.** UI never calls Claude or Deepgram directly — only via backend routes.
6. **Demo Mode is first-class.** A button that replays the scripted scenario via `transcript.segment` events at realistic timing. Test against Demo Mode before testing live mic.

---

## Why Not Other Patterns

| Pattern | Why Skip |
|---------|----------|
| **Pipeline / Chain** | Safety and Research must run in parallel with Documentation |
| **Monolithic orchestrator** | One person becomes bottleneck; merge conflicts |
| **Microservices** | Deployment complexity kills demo stability |
| **LangGraph / Agents SDK** | Extra abstraction layer; custom asyncio pub/sub is simpler |
| **Band SDK** | Redis pub/sub already coordinates agents; don't add a second orchestrator |

---

# Architecture

## Stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15 App Router, Tailwind |
| Backend | Python 3.11 · FastAPI · asyncio (port 8000) |
| API bridge | Next.js rewrites proxy `/api/*` → FastAPI |
| Event bus | Redis pub/sub (asyncio in-memory fallback) |
| State | Redis key-value per encounter (in-memory fallback) |
| Real-time UI | Server-Sent Events (`/api/events`) |
| LLM | Claude Sonnet (Anthropic Python SDK) |
| Voice | Deepgram streaming STT |
| Research | PubMed E-utilities + curated mock citations |
| Observability | Arize |

Single repo. Frontend on Vercel, backend on a Python host (Render / Railway / fly.io) + Redis Cloud.

---

## Frontend

Professional healthcare dashboard. Dark sidebar, clean typography, subtle clinical blue accents.

Persistent disclaimer banner at top: **"Demo only — not for clinical use."**

---

## Backend (`backend/`)

- `main.py` — FastAPI app entry point; starts all agents on boot via lifespan hook
- `routes/events.py` — `GET /api/events` — SSE stream; fan-out to all connected browsers
- `routes/encounter.py` — `POST/GET/DELETE /api/encounter` — start, status, reset
- `routes/transcript.py` — `POST /api/transcript` — ingest live transcript segments
- `routes/handoff.py` — `POST /api/handoff` — publish `handoff.requested`
- `routes/status.py` — `GET /api/status` — health check
- `routes/deepgram.py` — `GET /api/deepgram` — Deepgram key proxy
- `agents/` — one file per agent; each `async def start_*_agent(bus)` subscribes and returns an unsubscribe fn
- `redis_layer/` — async Redis client, key conventions, state persistence
- `sse/hub.py` — asyncio.Queue per SSE client; `broadcast_to_clients()` called by the event bus
- `events.py` — shared dataclasses (Python equivalent of `lib/events.ts`)

---

## Agent Layer

Custom orchestration only. Each agent is a Python module:

```
backend/agents/
  extraction.py      # debounced on transcript.segment → facts.extracted
  timeline.py        # facts.extracted → timeline.updated
  safety.py          # facts.extracted → safety.flagged
  documentation.py   # facts.extracted + timeline.updated → note.updated
  research.py        # facts.extracted (new med/allergy) → research.completed
  handoff.py         # handoff.requested → handoff.generated
```

Each file: `async def start_*_agent(bus) -> Callable` — subscribes to events, publishes results, returns an unsubscribe function.

Claude prompts and heuristic fallbacks live in `backend/prompts/` (one file per agent).

---

# Dashboard Layout

## Left Panel — Live Transcript

Streaming text. Speaker badges (Doctor / Patient). Auto-scroll.

## Center Panel — Patient Timeline

```
08:12  Patient reports acute chest pain, 2hr duration
08:14  Hypertension history identified
08:15  Warfarin medication discovered
08:16  ⚠ Safety: Anticoagulation + chest pain — ACS workup indicated
08:17  Left arm radiation noted
```

## Right Panel — AI Insights

- Active safety flags (severity color-coded)
- Missing information checklist
- Suggested follow-up questions
- Research citations (from Browserbase)

## Bottom Section — Live SOAP Note

Four sections update incrementally: Subjective, Objective, Assessment, Plan.

## Handoff Modal — Money Shot

Triggered by "Generate Handoff Report" button. Before/after view. **Final demo screen.**

---

# Demo Flow (5 minutes)

## Minute 1 — Problem

Doctors spend hours documenting. Information gets lost during handoffs. ER Copilot is a real-time AI clinical operations team.

## Minute 2 — Live conversation

Start scripted scenario (live mic or Demo Mode). Transcript streams. Timeline builds. Extraction populates entities.

## Minute 3 — Agents in action

Point to each panel updating in real time:

- Safety flag appears on warfarin mention
- Research citations load in insights panel
- SOAP note fills in bottom section

## Minute 4 — Handoff

Simulate shift change. Press "Generate Handoff Report." Show before (messy transcript) → after (structured report). **Stop here.**

## Minute 5 — Architecture (30 seconds max)

One slide or live diagram:

```
Deepgram → Redis Event Bus → 6 Agents → SSE /api/events → Dashboard
              ↕                ↕
           Claude           PubMed / mock citations
              ↕
            Arize
```

Mention only tools that visibly worked in the demo. Do not list six sponsor logos with no proof.

---

# Demo Mode (required)

Live mic fails. Demo Mode doesn't.

## Implementation

- `scripts/demo-scenario.json` — scripted beats with `{ text, speaker, delayMs }`
- Dashboard toggle: **Live** | **Demo**
- `POST /api/encounter` with `{ "mode": "demo" }` triggers `backend/demo/injector.py`
- Demo Mode publishes `transcript.segment` events through the same asyncio event bus
- All agents, SSE fan-out, and handoff work identically

## Rules

1. Rehearse the full pitch using Demo Mode at least twice before trying live mic.
2. Live mic is the wow moment during presentation — fall back to Demo Mode instantly if anything breaks.
3. Pre-recorded audio optional: play through Deepgram for extra sponsor points, but JSON injector is the reliable path.

---

# Build Schedule (36 hours)

| Hours | Milestone | Owner |
|-------|-----------|-------|
| **0–2** | Repo scaffold, `lib/events.ts`, Redis setup, empty dashboard shell, disclaimer banner | All |
| **2–6** | WebSocket + pub/sub working, Demo Mode injector, transcript panel live | Dev A |
| **2–6** | Extraction agent + Claude prompt (JSON schema), debounce buffer | Dev B |
| **2–6** | Dashboard layout (all 4 panels), mock data rendering | Dev C |
| **6–10** | Deepgram live mic integration | Dev A |
| **6–10** | Timeline + Safety agents wired to `facts.extracted` | Dev B |
| **6–10** | Documentation agent + SOAP panel live updates | Dev C |
| **10–14** | **Integration checkpoint:** Demo Mode → full pipeline → all panels update | All |
| **14–18** | Research agent (Browserbase), citations in insights panel | Dev C |
| **14–18** | Handoff agent + before/after modal | Dev C |
| **14–18** | Arize instrumentation on all Claude calls | Dev B |
| **18–22** | Polish UI, safety flag styling, timeline animations | Dev C |
| **18–22** | Prompt tuning against scripted scenario | Dev B |
| **18–22** | Live mic testing + Demo Mode fallback verification | Dev A |
| **22–28** | End-to-end demo rehearsals (minimum 3 full runs) | All |
| **28–32** | Bug fixes only. No new features. | All |
| **32–36** | Pitch prep, architecture slide, backup recording of Demo Mode | All |

**Hour 10 and hour 14 are hard integration checkpoints.** If the pipeline isn't working, stop all feature work and fix the bus.

---

# What Judges Care About

## Application

Real problem. Massive market. Easy to understand in 10 seconds.

## Functionality

Full product must be **stable**. A polished complete demo beats a buggy ambitious one. Demo Mode guarantees stability.

## Creativity

"Collaborative AI workforce for clinical operations." Not "healthcare chatbot."

## Technical Complexity

Visible in the demo, not just on slides:

- Real-time streaming (transcript)
- Six parallel agents (point to panels updating)
- External retrieval (Browserbase citations)
- Persistent memory (Redis encounter state)
- Monitoring (Arize trace for one extraction call)

---

# Elevator Pitch

ER Copilot is a real-time AI clinical operations assistant that listens to patient interactions, maintains a structured understanding of the case, coordinates six specialized agents to document and analyze information, and automatically generates shift handoff reports so clinicians can spend less time on paperwork and more time caring for patients.
