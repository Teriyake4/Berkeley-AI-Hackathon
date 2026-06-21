# CLAUDE.md — AI Assistant Entry Point

> **Read these first** to understand what this project is for, then open your dev track file.

## Required reading

1. **[ER_Copilot_Hackathon_Plan.md](./ER_Copilot_Hackathon_Plan.md)** — Source of truth for **Nos** (Ambulance Copilot): problem framing, agents, safety rules, demo beats, dashboard layout, sponsor tracks, and pitch structure.

2. **[Project_Context.md](./Project_Context.md)** — Short pointer to the plan plus links to dev tracks.

## Then pick your track

Each `docs/DEV_*.md` is your track-specific CLAUDE.md: checklist, file ownership, and Claude agent-team launch prompts.

| Dev | Track |
|-----|-------|
| **A** — Platform & ingestion | [docs/DEV_A.md](./docs/DEV_A.md) |
| **B** — Clinical brain & safety | [docs/DEV_B.md](./docs/DEV_B.md) |
| **C** — UI, research, CV & handoff | [docs/DEV_C.md](./docs/DEV_C.md) |

Parallel build coordination: [PARALLEL_BUILD.md](./PARALLEL_BUILD.md)

## Before editing shared code

Sync with teammates before changing `types/events.ts`, `lib/events.ts`, or `backend/events.py`.

## Coding conventions (summary)

- Structured JSON from LLM agents; idempotent entity merge.
- Safety flags only on **stated facts** — never demographic proxy alone.
- No diagnosis language in flags; use "consider …" / "verify …".
- Do not commit `.env` or secrets.
