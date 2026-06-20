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
