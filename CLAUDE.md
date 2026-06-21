Dev C — UI, Research, CV & Handoff
> **Use this file as your CLAUDE.md.**  
> **Project context:** [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md)
Branch: `dev/c-product`  
Mission: Make judges say wow — dashboard, Browserbase research, webcam scene capture, and the ambulance → hospital handoff money shot.
You do not touch the event bus, demo injector, or extraction/safety agent logic.
---
Your deliverables
[ ] Ambulance-themed dashboard — all panels update during demo
[ ] Research agent (Browserbase): injury protocols, drug interactions, unknown meds
[ ] CV capture — live webcam feed; Claude vision (VLM) scans pills, wounds, medical bracelets; results feed extraction + safety
[ ] UI note: "Production: chest- or helmet-mounted camera"
[ ] Insights panel shows safety trio + NREMT reminders + research citations
[ ] Live PCR/SOAP panel wired to `note.updated`
[ ] Handoff modal — paramedic → hospital report (end demo here)
[ ] Timeline shows GPS anchors + audio events + vision captures
[ ] 3 clean demo rehearsals with talking points
---
Files you own
```
app/page.tsx
app/layout.tsx
app/globals.css
components/**
  TranscriptPanel.tsx
  TimelinePanel.tsx
  InsightsPanel.tsx
  SoapPanel.tsx
  HandoffModal.tsx
  DisclaimerBanner.tsx
  VisionCapture.tsx          ← create
  TelemetryBar.tsx           ← create (optional)
hooks/useEncounterEvents.ts
lib/agents/research.ts
lib/agents/handoff.ts
lib/prompts/research.ts
lib/prompts/handoff.ts
app/api/handoff/route.ts
backend/agents/research.py
backend/agents/handoff.py
backend/agents/vision.py     ← create (CV upload → Claude vision)
backend/prompts/handoff.py
backend/prompts/research.py
backend/prompts/vision.py    ← create
backend/routes/vision.py     ← create (FastAPI router, POST /api/vision)
fixtures/full-encounter-state.json   (ambulance scenario)
```
Files you do NOT touch
```
lib/bus.ts
lib/redis/**              (read-only OK)
lib/demo/**
lib/sse/**
lib/agents/extraction.ts
lib/agents/timeline.ts
lib/agents/safety.ts
lib/agents/documentation.ts
scripts/demo-scenario.json  (coordinate with Dev A)
components/LiveMic.tsx
```
---
Build order
#	Task	Done when
1	Rebrand UI: Ambulance Copilot, paramedic/patient speakers	Static fixture looks like field tool
2	Wire `useEncounterEvents` to SSE	Demo updates all panels
3	Timeline: render GPS, audio events, vision entries	Multimodal timeline visible
4	Research agent + Browserbase	Warfarin beat → citations in insights
5	VisionCapture component + FastAPI endpoint	Live feed visible → identification → `vision.captured` → safety cross-check fires
6	Insights panel: safety severity colors + NREMT reminders + research	All three demo flags visible
7	Handoff modal — before (raw transcript) / after (structured hospital report)	Pitch ends here
8	Polish + demo script	5-min flow rehearsed 3×
---
Research agent (Browserbase)
Triggers:
New medication in `facts.extracted` not yet researched
New allergy or high-risk condition
Paramedic explicitly uncertain ("I don't know what this pill is") — extract from transcript
Queries (examples):
`warfarin aspirin interaction bleeding risk`
`chest pain prehospital ACS guideline`
`{unknown_pill_imprint} pill identifier`
Publish `research.completed` with 2–3 citations. Display under References in insights. Citations also carry through to the handoff report (see below) — don't let this dead-end in the insights panel only.
Paramedics can ask questions themselves in dialogue; research backs them up so the handoff doc includes everything the ED doctor needs.
---
Computer vision (demo)
Approach: VLM (Claude vision), not a trained detector
We're using Claude's vision API on captured frames — not a custom-trained object detection model. No labeled dataset, no training time, and the task is read-and-reason ("what does this label say") more than pure detection, which a VLM handles natively. Same pipeline serves pills, bracelets, and wounds — just a different prompt per type, not separate models.
UX
Live webcam feed runs continuously in the UI (visible to the demo operator/paramedic at all times, not just on a button press) — this is the "ambient, hands-free" feel that matches the pitch.
No manual "Scan scene" button as the primary flow. Capture is automatic:
Baseline interval capture: grab a frame every ~4s as a fallback so nothing sits unnoticed too long.
Stability-triggered capture: lightweight client-side motion detection (canvas pixel diff between frames) — when motion drops to near-zero after a period of motion (something held steady in frame), fire an immediate capture. This is the primary trigger for the demo beat (holding up a vial).
Sustained-hold re-capture: if an object stays steady in frame for an extended period (e.g., >3s), capture again at a fixed cadence (e.g., every 2s) while it remains steady, in case the first frame was blurry/misangled or partially occluded. Stop re-capturing once motion resumes or the object leaves frame.
Gate all captures so we're not spamming the API on every camera frame — only the interval tick and the stability/sustained triggers above call the vision endpoint.
Use cases in demo: pill vial, medical alert bracelet, visible wound (optional).
Caption in UI: "Demo uses laptop camera. In the field: chest-mounted body cam."
Capture confirmation lives in the transcript panel, not on the video feed. When a capture resolves, inject a line into the same scrolling transcript as the paramedic/patient dialogue — styled distinctly (e.g., a "Console" or "Vision" speaker label) so it reads as a third voice in the conversation log rather than a UI overlay:
```
  Paramedic: "Let me check what she's taking."
  Patient: "I've got the Tylenol in my bag..."
  Console: Observing — Tylenol (acetaminophen) identified.
  ```
No bounding boxes or labels drawn on the live video itself — keep the feed clean, all feedback goes through this transcript line. This is also the easiest place to make the capture feel "ambient" rather than like a system event, since it just appears in the same flow as everything else being said.
Flow
Live feed running in `VisionCapture.tsx` → frame extracted client-side (canvas) on interval or motion trigger
Frame → `POST /api/vision` (base64 JPEG) — FastAPI backend, not a Next.js route
`backend/routes/vision.py` → `backend/agents/vision.py` → Claude vision call → structured JSON: `{ identified: boolean, type: "medication"|"bracelet"|"wound"|"none", label_text: string|null, confidence: "high"|"medium"|"low" }`
Only `confidence: "high"|"medium"` results proceed — discard `"low"` silently (avoid misread labels reaching the safety agent)
Backend publishes `vision.captured` to the event bus + merges into entities
Frontend receives `vision.captured` over SSE → injects the "Console: Observing — X identified" line into the transcript panel (see UX above)
Dev B safety agent cross-checks med vs. known list → insights flag
Result also flows into timeline (vision entry) and handoff report (current medications: stated + vision-identified) — see Handoff section
Demo beat: Patient on warfarin → paramedic holds up aspirin vial, holds steady → stability trigger fires capture → interaction flag appears before aspirin is given.
Claude vision call (reference)
```python
# backend/agents/vision.py — FastAPI backend, server-side only
import os
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

VISION_PROMPT = (
    "Look at this image from an ambulance cabin camera. Identify if it shows: "
    "a medication vial/bottle/ampoule (read the label if legible), a medical "
    "alert bracelet, or a visible wound/injury. Respond ONLY with JSON, no "
    "other text: {\"identified\": boolean, \"type\": \"medication\"|\"bracelet\"|"
    "\"wound\"|\"none\", \"label_text\": string|null, \"confidence\": \"high\"|"
    "\"medium\"|\"low\"}"
)

def identify_frame(frame_base64: str) -> dict:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": frame_base64}},
                {"type": "text", "text": VISION_PROMPT},
            ],
        }],
    )
    # parse response.content[0].text as JSON, publish vision.captured if confidence is high/medium
    ...
```
```python
# backend/routes/vision.py — FastAPI router
from fastapi import APIRouter
from backend.agents.vision import identify_frame

router = APIRouter()

@router.post("/api/vision")
async def scan_frame(payload: dict):
    result = identify_frame(payload["frame_base64"])
    # if result["confidence"] in ("high", "medium"): publish vision.captured to event bus
    return result
```
Client (`VisionCapture.tsx`) calls `POST /api/vision` on the FastAPI backend (not a Next.js route) — confirm the backend base URL with Dev A (likely proxied or CORS-enabled for local dev). Never call Claude directly from the client; the key stays server-side in the FastAPI process.
---
Handoff report (money shot)
Ambulance always hands off to hospital. Report must include:
Patient summary + chief complaint
Allergies (prominent)
Timeline with GPS-anchored timestamps
Current medications (stated + vision-identified — tag source so ED knows what came from the camera vs. verbal)
Outstanding questions
Recommended ED actions
Research citations for high-risk findings
Flow:
Click Generate Handoff Report
`POST /api/handoff` → `handoff.requested`
Handoff agent → `handoff.generated`
Modal: messy transcript | structured report — stop demo here
---
Dashboard layout
```
┌──────────────────────────────────────────────────────────────┐
│ ⚠ Demo only — not for clinical use.     [Live | Demo]         │
├──────────────┬──────────────────────────┬────────────────────┤
│  Transcript  │  Timeline (+ GPS/audio)  │  AI Insights       │
│  paramedic/  │                          │  flags · NREMT ·   │
│  patient     │                          │  research refs     │
├──────────────┼──────────────────────────┴────────────────────┤
│  Live camera feed (small, persistent) │  Live PCR / SOAP note │
├──────────────────────────────────────────────────────────────┤
│  Scene · En route · Hospital          [ Generate Handoff ]    │
└──────────────────────────────────────────────────────────────┘
```
Note: dropped the explicit `[📷 Scan]` button from the header — capture is now automatic/ambient via the persistent live feed panel, not a manual trigger. Keep a small manual "capture now" affordance as a fallback in `VisionCapture.tsx` in case the auto-trigger misses something during the demo, but it shouldn't be the primary flow shown to judges.
---
Panel → event mapping
Panel	Events
Transcript	`transcript.segment`
Timeline	`timeline.updated`, `telemetry.updated`, `audio.event`, `vision.captured`, `safety.flagged`
Insights	`safety.flagged`, `research.completed`, NREMT reminders
SOAP	`note.updated`
Handoff modal	`handoff.generated`
Live camera feed	local only (no event needed — raw `getUserMedia` stream)
---
Demo script (you lead pitch)
Min	Action	Call out
0–1	Problem: information lost between scene and ED	—
1–2	Start demo — paramedic assesses chest pain	Transcript + timeline
2–3	Allergies + warfarin extracted	Allergy line in note
3–4	Missed follow-up flag appears	"Agent remembered chest pain from 3 min ago"
4	Hold aspirin vial steady in front of live feed	CV auto-captures + interaction flag fires
5	Research citations	Browserbase
5	Handoff modal	End — no architecture slide
---
Env vars
```bash
ANTHROPIC_API_KEY=        # server-side only — .env.local, gitignored, never sent to client
BROWSERBASE_API_KEY=
BROWSERBASE_PROJECT_ID=
ARIZE_SPACE_ID=          # optional
ARIZE_API_KEY=
```
API key handling: key lives in `.env` on the FastAPI backend (gitignored). All Claude calls — vision, research, handoff — happen server-side in `backend/agents/*.py`, never called directly from client components. Confirm `.env` is in `.gitignore` before first commit. If sharing one key across the team, distribute it out-of-band (Slack DM/etc.), not in the repo.
---
Test in isolation (hour 0–6)
Render from `fixtures/full-encounter-state.json` before SSE is ready.
Mock `vision.captured` dispatch in reducer to build Insights panel early. Mock the live feed with a static placeholder/looping clip if camera permissions or hardware aren't sorted yet — don't block UI work on having a working webcam pipeline.
---
Reference
ER_Copilot_Hackathon_Plan.md — project context (read first)
DEV_A.md · DEV_B.md
PARALLEL_BUILD.md
Shared contract: `lib/events.ts` — sync before changing
---
Claude Agent Team (parallel sub-agents)
Prepend to every launch prompt:
```
First read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md.
```
Phase	Run in parallel	Wait for
0	Agents 1 + 2	— (fixtures only)
1	Agent 3	Agent 1 layout exists
2	Agents 4 + 5 + 6	Agent 3 SSE wired
3	Agent 7	Agents 4–6 functional
4	Agent 8	Full pipeline
Agent 1 — Dashboard Shell
Launch prompt:
```
You are Dashboard Shell agent on Ambulance Copilot (Dev C, Agent 1).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Rebrand UI to Ambulance Copilot; render fixtures/full-encounter-state.json statically.
```
Agent 2 — Event Reducer & SSE Hook
Launch prompt:
```
You are Event Reducer agent on Ambulance Copilot (Dev C, Agent 2).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement hooks/useEncounterEvents.ts for all event channels including audio.event, telemetry.updated, vision.captured.
```
Agent 3 — Multimodal Timeline UI
Launch prompt:
```
You are Multimodal Timeline UI agent on Ambulance Copilot (Dev C, Agent 3).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Extend TimelinePanel + TelemetryBar for GPS, audio, and vision entries.
```
Agent 4 — Research + Browserbase
Launch prompt:
```
You are Research agent on Ambulance Copilot (Dev C, Agent 4).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement backend/agents/research.py with Browserbase when keyed, fallback otherwise.
```
Agent 5 — Vision Capture
Launch prompt:
```
You are Vision Capture agent on Ambulance Copilot (Dev C, Agent 5).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Build VisionCapture.tsx with a persistent live webcam feed, client-side motion/stability detection, interval + trigger-based frame capture, and a POST to the FastAPI backend's /api/vision route (backend/routes/vision.py + backend/agents/vision.py). Vision agent calls Claude vision API server-side and publishes vision.captured. On capture, frontend should render a "Console: Observing — {item} identified" line in the transcript panel. Never expose ANTHROPIC_API_KEY to the client.
```
Agent 6 — Handoff Modal
Launch prompt:
```
You are Handoff agent on Ambulance Copilot (Dev C, Agent 6).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Implement handoff agent + HandoffModal before/after split. End demo on this screen.
```
Agent 7 — Insights Panel Polish
Launch prompt:
```
You are Insights Polish agent on Ambulance Copilot (Dev C, Agent 7).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Polish InsightsPanel: safety colors, NREMT reminders, research citations.
```
Agent 8 — Demo & Pitch Integration
Launch prompt:
```
You are Demo Integration agent on Ambulance Copilot (Dev C, Agent 8).
Read ER_Copilot_Hackathon_Plan.md and docs/DEV_C.md. Verify full 5-min demo flow; polish ModeToggle. Fix only Dev C files.
```

<frontend_aesthetics>
You tend to converge toward generic, "on distribution" outputs. In frontend design, this creates what users call the "AI slop" aesthetic. Avoid this: make creative, distinctive frontends that surprise and delight. Focus on:

Typography: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics.

Color & Theme: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes. Draw from IDE themes and cultural aesthetics for inspiration.

Motion: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions.

Backgrounds: Create atmosphere and depth rather than defaulting to solid colors. Layer CSS gradients, use geometric patterns, or add contextual effects that match the overall aesthetic.

Avoid generic AI-generated aesthetics:
- Overused font families (Inter, Roboto, Arial, system fonts)
- Clichéd color schemes (particularly purple gradients on white backgrounds)
- Predictable layouts and component patterns
- Cookie-cutter design that lacks context-specific character

Interpret creatively and make unexpected choices that feel genuinely designed for the context. Vary between light and dark themes, different fonts, different aesthetics. You still tend to converge on common choices (Space Grotesk, for example) across generations. Avoid this: it is critical that you think outside the box!
</frontend_aesthetics>
