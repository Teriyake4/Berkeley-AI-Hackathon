# Nos — Demo Runbook & Pitch Script
> Nos: AI Paramedic Copilot (ambulance theme).

> Money shot: paramedic on scene → AI catches a warfarin+aspirin interaction the
> moment a vial is seen → structured handoff lands in the ED's hands.
> **End on the handoff modal. No architecture slide.**

---

## 0. Pre-flight (do this before judges sit down)

1. **Start the backend** (FastAPI, port 8000):
   ```bash
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Start the frontend** (Next.js, port 3000):
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000`. Confirm:
   - Header reads **🚑 Nos** (dark-red bar).
   - Connection chip says **● Connected** (green). If red/reconnecting, the backend isn't up.
4. **Keys** (`.env` at repo root, gitignored): `ANTHROPIC_API_KEY` is the only one that
   materially changes the demo. Without it, agents use heuristic fallbacks (still works,
   slightly less polished SOAP/handoff text). `BROWSERBASE_API_KEY` + `BROWSERBASE_PROJECT_ID`
   light up live web citations; without them research falls back to PubMed/curated citations.
5. **Camera**: grant the browser camera permission once, up front, so there's no permission
   popup mid-pitch. If you'll use the *live* vial trick, have a real aspirin/Tylenol bottle ready.
6. Do a **throwaway run** (click Demo, let it play 20s, then refresh) so the first-call model
   latency is warm.

---

## 1. The 5-minute pitch

| Min | You say (talking points) | You click / do | On-screen cue to point at |
|-----|--------------------------|----------------|----------------------------|
| **0–1** | "Every year, critical patient info gets lost in the handoff between the ambulance and the ER. The paramedic's hands are full; the story lives in their head. We built an AI teammate that rides along — it listens, watches, researches, and writes the handoff for them." | — | The idle dashboard. Gesture at the empty panels: transcript, timeline, insights, camera, PCR note. |
| **1–2** | "Here's a 67-year-old with sudden chest pain. Watch the left column — that's the live conversation being transcribed, and the timeline is anchoring every event with GPS and time." | Click **Demo** | Transcript fills (Paramedic/Patient). Timeline shows **📍 Scene arrival**. Bottom **Scene** stage lights up. Agent strip flickers green. |
| **2–3** | "The extraction agent is pulling structured facts in real time — no typing. It just caught a **penicillin allergy** and that she's on **warfarin** for a heart valve." | — | "EXTRACTED" chip bar: `⚠ penicillin allergy`, `warfarin`, `chest pain`. SOAP note auto-populates. |
| **3–4** | "Now the safety agent does what a stressed human forgets. It flagged that chest pain was mentioned three minutes ago and hasn't been reassessed — and it's tracking NREMT protocol gaps." | — | Insights panel: a **medium** missed-follow-up flag + **NREMT Reminders** checklist. Timeline **🔊** ECG audio event. Bottom **En route** lights up. |
| **4** | "The patient had a med bag. The camera — in production a chest- or helmet-mounted body cam — sees an **aspirin** bottle. Aspirin plus warfarin is a serious bleeding risk. The AI catches it **before** anyone hands her a pill." | *(Demo mode auto-fires this at ~3:30.)* **Optional live:** hold a vial steady to the webcam | Transcript shows **📷 Console: Observing — aspirin 325mg identified.** Timeline **📷** vision entry. Insights: **🚨 HIGH** "patient is on warfarin (bleeding risk)" flag. |
| **5** | "Everything it found is backed by live research the paramedic never had to stop and look up." Then: "And here's the payoff — one click turns four minutes of chaos into a clean, structured handoff the receiving ED can act on instantly." | Click **Generate Handoff Report** | Insights **Research** section with citations. Modal opens: **left = raw transcript, right = structured handoff** — allergies in red, meds tagged 📷 camera vs stated, outstanding questions, recommended ED actions. |

**Close on the handoff modal.** Last line: *"Scene to ED, nothing lost. That's Nos."*

---

## 2. What fires when (injector timeline, Demo mode)

The Demo button replays `scripts/demo-scenario.json` (~4 min total). Key beats:

- `0:00` 📍 Scene arrival (telemetry → Scene phase)
- `0:37` Patient states **warfarin** + heart valve → extraction → SOAP/insights update
- `1:18` 🔊 12-lead ECG audio event
- `2:10` 🚑 En route (telemetry → En route phase)
- `~3:00` ⚠ Missed-follow-up flag for chest pain (3-min reassessment timer)
- `3:30` 📷 **Vision: aspirin 325mg** → 🚨 HIGH warfarin interaction flag (the money beat)
- `4:00` 🏥 Hospital arrival (telemetry → Hospital phase)

You do **not** have to wait the full 4 minutes — once the aspirin flag has fired (~3:30) you can
jump straight to **Generate Handoff** any time.

---

## 3. Live camera variant (higher risk, higher wow)

Instead of relying on the injector's scripted vision beat, you can trigger it for real:

1. Make sure the **Live Camera Feed** panel shows your webcam and the status dot reads **Monitoring**.
2. While the demo is running and warfarin has already been extracted, **hold an aspirin/Tylenol
   bottle steady** in frame. Motion-settle detection fires a capture automatically; a
   `📷 Console:` line appears in the transcript and the safety flag follows.
3. Fallback: click **Capture now** under the feed if the auto-trigger misses.

> Only use the live variant if you've rehearsed it and `ANTHROPIC_API_KEY` is set (the vision
> call is Claude server-side). Otherwise stick to Demo mode — the scripted beat is identical
> on screen and 100% reliable.

---

## 4. Rehearsal checklist (run 3×)

- [ ] **Run 1 — timing:** click Demo, narrate the table above, confirm every cue appears. Note
      where the aspirin flag lands relative to your script so you can pace your patter.
- [ ] **Run 2 — handoff:** let it run to the aspirin flag, click Generate Handoff, read the
      structured report aloud. Confirm allergies are red, the aspirin med is tagged `📷 camera`,
      and research citations are present.
- [ ] **Run 3 — recovery:** practice the failure paths below so nothing rattles you live.
- [ ] Hard-refresh between runs (the dashboard resets on a new Demo click, but a clean reload
      guarantees a fresh SSE connection).

---

## 5. If something breaks (stay calm, keep talking)

| Symptom | Cause | Live fix |
|---------|-------|----------|
| Connection chip red | Backend down or restarting | Keep narrating the problem statement; it auto-reconnects every 3s. |
| Panels empty after clicking Demo | SSE not connected yet | Click Demo again; it re-resets and replays. |
| No aspirin/safety flag | `ANTHROPIC_API_KEY` unset → heuristic path | Heuristics still fire the warfarin+aspirin flag; just confirm warfarin was extracted first. |
| Camera popup / black feed | Permission not pre-granted | Ignore it — say "in production this is a body cam," and rely on Demo mode's scripted vision beat. |
| Handoff slow to generate | First Claude call cold | "It's synthesizing the full encounter" — the spinner is on-brand; it lands in a few seconds. |
| Research citations missing | No Browserbase/PubMed reachable | Curated fallback citations still render; don't dwell, move to the handoff. |

---

## 6. One-liner backups (if asked)

- **"Is the camera trained on pills?"** No — it's Claude's vision model reading labels and
  reasoning, so the same pipeline handles vials, medical-alert bracelets, and wounds with just
  a different prompt. No dataset, no training.
- **"Where does the research come from?"** Live web search through a Browserbase cloud browser
  when keyed, with PubMed and curated clinical guidelines as fallback — and it flows into the
  handoff, not just the screen.
- **"Is this making medical decisions?"** No. It's a documentation and safety-net teammate.
  Every screen carries the "demo only, not for clinical use" banner.
