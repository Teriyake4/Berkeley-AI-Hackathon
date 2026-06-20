# ER Copilot

Real-time AI clinical operations assistant — Berkeley AI Hackathon.

## Quick start

Two terminals required — Python backend + Next.js frontend.

**Terminal 1 — Python backend:**
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example ../.env          # add API keys (all optional — heuristics work offline)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Next.js frontend:**
```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) → click **Demo** → watch all agents work → **Generate Handoff Report**.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  (Next.js frontend — TypeScript/React, port 3000)  │
└──────────────────────┬──────────────────────────────────────┘
                       │ /api/* (proxied via next.config.ts)
┌──────────────────────▼──────────────────────────────────────┐
│  Python FastAPI backend  (port 8000)                        │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │ Event Bus   │    │  6 Agents    │    │  SSE Hub      │  │
│  │ (Redis or   │───▶│  extraction  │───▶│  /api/events  │  │
│  │  in-memory) │    │  timeline    │    └───────────────┘  │
│  └─────────────┘    │  safety      │                       │
│                     │  docs        │    ┌───────────────┐  │
│  ┌─────────────┐    │  research    │    │  State Store  │  │
│  │  Claude     │───▶│  handoff     │───▶│  (Redis or    │  │
│  │  (optional) │    └──────────────┘    │   in-memory)  │  │
│  └─────────────┘                        └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

- **Backend:** Python 3.11+ · FastAPI · asyncio
- **Event bus:** Redis pub/sub (in-memory fallback)
- **Real-time UI:** Server-Sent Events (`/api/events`)
- **6 agents:** extraction, timeline, safety, documentation, research, handoff
- **Demo Mode:** replays `scripts/demo-scenario.json`
- **Live Mode:** browser mic via Web Speech API → `/api/transcript`

## Project structure

```
backend/                  # Python FastAPI backend (replaces lib/ + app/api/)
  main.py                 # FastAPI app entry point
  events.py               # Shared event dataclasses
  bus.py                  # Event bus (Redis or in-memory)
  claude.py               # Anthropic Claude wrapper
  debounce.py             # Async debounce utility
  redis_layer/            # Redis client, keys, state persistence
  sse/                    # SSE fan-out hub
  agents/                 # 6 async agents
  prompts/                # Claude prompts + heuristic fallbacks
  demo/                   # Demo scenario replay
  routes/                 # FastAPI route handlers

app/                      # Next.js frontend (UI only)
  page.tsx                # Main dashboard
  layout.tsx

components/               # React UI panels
hooks/                    # useEncounterEvents (SSE client)
scripts/
  demo-scenario.json      # Demo encounter dialogue script
```

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js frontend (port 3000) |
| `npm run typecheck` | TypeScript check |
| `uvicorn main:app --reload` | Start Python backend (run from `backend/`) |

## API keys

All optional for demo. Without keys, heuristic fallbacks produce a working demo.

| Key | Enables |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude-powered extraction, SOAP, handoff |
| `DEEPGRAM_API_KEY` | Deepgram STT (Live mode uses Web Speech API without it) |
| `REDIS_URL` | Persistent state + multi-instance pub/sub |
| `BROWSERBASE_API_KEY` | Live web research (mock citations without it) |

## Docs

- [Backend README](./backend/README.md)
- [Teammate 1 — Platform & Pipeline](./docs/TEAMMATE_1.md)
- [Teammate 2 — Agents, UI & Demo](./docs/TEAMMATE_2.md)
- [Product plan](./ER_Copilot_Hackathon_Plan.md)
