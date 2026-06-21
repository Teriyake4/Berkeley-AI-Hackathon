# CLAUDE.md — AI Assistant Entry Point

> **Read these first** to understand what this project is for, then open your dev agent-team file.

## Required reading

1. **[Project_Context.md](./Project_Context.md)** — Current product scope: **Ambulance Copilot** pivot, core agents, safety rules, demo trio, multimodal inputs, repo layout, and integration gates. **This is the source of truth for what we are building now.**

2. **[ER_Copilot_Hackathon_Plan.md](./ER_Copilot_Hackathon_Plan.md)** — Original UC Berkeley hackathon plan: problem framing, full product scope, scripted demo beats, dashboard layout, sponsor tracks, and pitch structure. Use alongside Project_Context for demo flow and judging criteria (note: we pivoted from ER to ambulance; Project_Context wins on scope conflicts).

## Then pick your track

| Dev | Human checklist | Agent team (parallel sub-agents) |
|-----|-----------------|----------------------------------|
| **A** — Platform & ingestion | [docs/DEV_A.md](./docs/DEV_A.md) | [docs/Claude_DEV_A.md](./docs/Claude_DEV_A.md) |
| **B** — Clinical brain & safety | [docs/DEV_B.md](./docs/DEV_B.md) | [docs/Claude_DEV_B.md](./docs/Claude_DEV_B.md) |
| **C** — UI, research, CV & handoff | [docs/DEV_C.md](./docs/DEV_C.md) | [docs/Claude_DEV_C.md](./docs/Claude_DEV_C.md) |

Parallel build coordination: [PARALLEL_BUILD.md](./PARALLEL_BUILD.md)

## Before editing shared code

Sync with teammates before changing `lib/events.ts` or `backend/events.py`.

## Coding conventions (summary)

- Structured JSON from LLM agents; idempotent entity merge.
- Safety flags only on **stated facts** — never demographic proxy alone.
- No diagnosis language in flags; use "consider …" / "verify …".
- Do not commit `.env` or secrets.
