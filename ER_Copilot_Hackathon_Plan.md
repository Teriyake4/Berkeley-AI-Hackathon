# ER Copilot — AI Clinical Operations Assistant
## UC Berkeley AI Hackathon Project Plan

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

# Core Demo

## Scenario

A doctor and patient are having a conversation.

Doctor:

> 67-year-old male with chest pain.
> History of hypertension.
> Taking warfarin.

As the conversation happens:

### Agent 1
Transcribes speech live.

### Agent 2
Extracts medical facts.

### Agent 3
Builds a structured timeline.

### Agent 4
Looks for potential concerns.

### Agent 5
Creates documentation.

### Agent 6
Prepares handoff summaries.

All update live.

---

# The Money Shot

At the end of the demo:

Display:

## Before

Messy transcript.

## After

Perfect shift handoff report.

Including:

- Patient summary
- Timeline
- Current medications
- Outstanding questions
- Recommended next actions

This should be the final screen judges see.

---

# Tracks To Target

## Anthropic

Strongest target.

Reasons:

- Healthcare impact
- Meaningful societal value
- Complex reasoning
- Heavy Claude usage

Use Claude for:

- Structured extraction
- Summaries
- Timeline generation
- Safety checks
- Handoff generation

---

## Deepgram

Likely highest probability sponsor prize.

Use:

- Streaming Speech-to-Text
- Speaker diarization

Voice should be central to the product.

Without Deepgram the demo should not work.

---

## Browserbase

Use Browserbase agents for:

- Guideline lookup
- Drug interaction research
- Literature retrieval
- Evidence gathering

Example:

Doctor mentions a medication.

Research agent automatically finds:

- Risks
- Contraindications
- Supporting references

---

## Redis

Use Redis for:

- Agent memory
- Timeline storage
- Vector retrieval
- Context persistence

Show architecture clearly.

---

## Band

Create multiple collaborating agents.

Example:

Transcriber Agent
↓
Timeline Agent
↓
Documentation Agent
↓
Safety Agent
↓
Research Agent

Band coordinates communication.

---

## Arize

Track:

- Latency
- Extraction accuracy
- Hallucination rate

Easy integration.

Good sponsor alignment.

---

# Design Pattern: Event-Driven Architecture (Pub/Sub)

## Why This Pattern

Three vibe coders building six agents in parallel will collide fast without a shared contract. **Event-Driven Architecture** gives everyone the same rule:

> Agents don't call each other directly. They publish events. Other agents subscribe and react.

This matches the product (clinical events happen continuously), the stack (Redis pub/sub + WebSocket fan-out), and the demo narrative ("collaborative AI workforce reacting in real time").

---

## Core Idea

```
Deepgram → transcript.segment
              ↓
         [Event Bus — Redis]
         ↙    ↓    ↓    ↘
   extraction  timeline  safety  documentation
         ↓         ↓        ↓          ↓
    facts.extracted  timeline.updated  safety.flagged  note.updated
              ↓
         [WebSocket → Frontend]
```

Every state change is an **event** with a typed payload. Agents are **dumb subscribers** — easy to vibe-code in isolation because the only contract is the event schema.

---

## Event Schema (MVP)

Keep events small and versioned. Example types:

| Event | Publisher | Payload |
|-------|-----------|---------|
| `transcript.segment` | Voice layer | `{ text, speaker, timestamp }` |
| `facts.extracted` | Extraction agent | `{ entities: Medication[], Condition[], ... }` |
| `timeline.updated` | Timeline agent | `{ events: TimelineEntry[] }` |
| `safety.flagged` | Safety agent | `{ concern, severity, rationale }` |
| `note.updated` | Documentation agent | `{ soap: { S, O, A, P } }` |
| `handoff.requested` | Frontend | `{ encounterId }` |
| `handoff.generated` | Handoff agent | `{ report: HandoffReport }` |

Define these in one shared `events.ts` (or `events.py`) file on day one. Never change field names mid-hackathon — add new events instead.

---

## Three-Dev Split

| Dev | Owns | Subscribes To | Publishes |
|-----|------|---------------|-----------|
| **Dev A — Voice & Ingest** | Deepgram integration, WebSocket server, event bus setup | — | `transcript.segment` |
| **Dev B — Agent Brain** | Extraction, Timeline, Safety, Documentation agents | `transcript.segment` | `facts.extracted`, `timeline.updated`, `safety.flagged`, `note.updated` |
| **Dev C — Dashboard** | Next.js UI, live panels, handoff button | All agent events (via WebSocket) | `handoff.requested` |

Each dev can prompt AI against their slice without touching the others' code. Integration happens through the event bus, not function imports.

---

## Rules for Vibe Coding

1. **No direct agent-to-agent imports.** If Agent B needs transcript data, subscribe to `transcript.segment` — don't import Agent A's module.
2. **One shared event types file.** First commit of the hackathon. Everyone imports from it.
3. **Idempotent handlers.** Events may replay; agents should upsert state, not append blindly.
4. **Redis = source of truth.** Pub/sub for live updates; Redis keys for encounter state so a refresh doesn't lose the case.
5. **Frontend is read-only + triggers.** UI never runs Claude or Deepgram — it publishes `handoff.requested` and renders whatever events arrive.

---

## Why Not Other Patterns

| Pattern | Why Skip |
|---------|----------|
| **Pipeline / Chain** | Too rigid — Safety and Research agents need to run in parallel, not in sequence |
| **Monolithic orchestrator** | One person becomes the bottleneck; merge conflicts on the orchestrator file |
| **Microservices** | Overkill for 36 hours; deployment complexity kills demo stability |
| **Blackboard** | Conceptually similar, but pub/sub *is* the blackboard mechanism here — use the clearer name |

---

# Architecture

## Frontend

- Next.js
- Tailwind
- shadcn/ui

Goal:

Look like a professional healthcare dashboard.

---

## Backend

- Next.js API routes or FastAPI
- WebSocket streaming

---

## AI Layer

Claude Sonnet

Responsibilities:

- Medical entity extraction
- Summaries
- Handoff reports
- Clinical reasoning

---

## Voice Layer

Deepgram

Responsibilities:

- Live transcription
- Speaker separation

---

## Agent Layer

Possible implementation:

- LangGraph
or
- OpenAI Agents SDK
or
- Custom orchestration

Agents:

1. Transcription Agent
2. Fact Extraction Agent
3. Timeline Agent
4. Safety Agent
5. Documentation Agent
6. Research Agent

---

# Dashboard Layout

## Left Panel

Live Transcript

---

## Center Panel

Patient Timeline

Example:

08:12
Patient reports chest pain

08:14
Hypertension history identified

08:15
Warfarin medication discovered

---

## Right Panel

AI Insights

- Potential concerns
- Missing information
- Suggested follow-up questions

---

## Bottom Section

Live SOAP Note

Automatically generated.

---

# Demo Flow

## Minute 1

Introduce problem.

Doctors spend hours documenting.

Information gets lost during handoffs.

---

## Minute 2

Start conversation.

Deepgram transcribes.

Timeline builds itself.

---

## Minute 3

Show agents working.

Research agent retrieves references.

Safety agent flags concerns.

Documentation agent updates notes.

---

## Minute 4

Simulate shift change.

Press:

"Generate Handoff Report"

Instantly produce structured report.

---

## Minute 5

Show architecture.

Demonstrate:

- Claude
- Deepgram
- Browserbase
- Redis
- Band
- Arize

---

# Stretch Features

## Voice Mode

Doctor can ask:

"What medications is this patient currently taking?"

Agent answers immediately.

---

## Patient Memory

Past visits stored.

Agent remembers prior conversations.

---

## Risk Timeline

Visual severity score over time.

---

## Differential Diagnosis Generator

Not actual diagnosis.

Only educational suggestions.

---

## Multi-Patient Dashboard

Track multiple active patients.

Looks very impressive visually.

---

# What Judges Care About

## Application

Real problem.

Massive market.

Easy to understand.

---

## Functionality

Prioritize:

- Stable demo
- Fast response times
- Beautiful UI

Over complex features.

---

## Creativity

Emphasize:

"Collaborative AI workforce for clinical operations."

Not:

"Healthcare chatbot."

---

## Technical Complexity

Show:

- Real-time streaming
- Agent orchestration
- Retrieval
- Memory
- Monitoring

---

# MVP Priorities

If time is short:

Build only:

1. Deepgram transcription
2. Claude extraction
3. Live timeline
4. Handoff report

Everything else is optional.

These four features alone can produce a winning demo.

---

# Elevator Pitch

ER Copilot is a real-time AI clinical operations assistant that listens to patient interactions, maintains a structured understanding of the case, coordinates specialized agents to document and analyze information, and automatically generates shift handoff reports so clinicians can spend less time on paperwork and more time caring for patients.
