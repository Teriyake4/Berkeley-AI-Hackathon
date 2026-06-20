# ER Copilot

Real-time AI clinical operations assistant — Berkeley AI Hackathon.

## Quick start

```bash
cp .env.example .env.local   # add API keys (all optional — heuristics work offline)
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) → click **Demo** → watch all agents work → **Generate Handoff Report**.

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js app |
| `npm run local-bus` | Test agents in terminal (no UI) |
| `npm run typecheck` | TypeScript check |

## Architecture

- **Event bus:** Redis pub/sub (in-memory fallback)
- **Real-time UI:** Server-Sent Events (`/api/events`)
- **6 agents:** extraction, timeline, safety, documentation, research, handoff
- **Demo Mode:** replays `scripts/demo-scenario.json`
- **Live Mode:** browser mic via Web Speech API → transcript API

## Docs

- [Teammate 1 — Platform & Pipeline](./docs/TEAMMATE_1.md)
- [Teammate 2 — Agents, UI & Demo](./docs/TEAMMATE_2.md)
- [Product plan](./ER_Copilot_Hackathon_Plan.md)
- [Parallel build guide](./PARALLEL_BUILD.md)

## API keys

All optional for demo. Without keys, heuristic fallbacks produce a working demo.

| Key | Enables |
|-----|---------|
| `ANTHROPIC_API_KEY` | Claude-powered extraction, SOAP, handoff |
| `DEEPGRAM_API_KEY` | Deepgram STT (Live mode uses Web Speech API without it) |
| `REDIS_URL` | Persistent state + multi-instance pub/sub |
| `BROWSERBASE_API_KEY` | Live web research (mock citations without it) |
