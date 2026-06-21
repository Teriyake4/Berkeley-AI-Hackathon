# Ambulance Copilot — Demo Script (Primary)

> **Machine replay:** `scripts/demo-scenario.json` (~20s, 1s between beats)  
> **UI:** Click **Demo** → watch panels update → **Generate Handoff Report** to end

Use this for rehearsals, prompt tuning, and judge-facing talking points.

---

## One-liner (10 seconds)

Paramedics multitask under pressure. Information gets lost between the scene and the ED. Ambulance Copilot listens, captures context, flags what gets missed, and writes the hospital handoff — so nothing falls through the cracks.

---

## 5-minute pitch flow

| Time | You say / do | Point at |
|------|----------------|----------|
| **0:00** | Problem: scene → ambulance → ED handoff is where details die. | — |
| **0:30** | Click **Demo**. | Transcript panel |
| **0:45** | "Chest pain, two hours, gardening — captured live." | Timeline |
| **1:00** | "Allergies and meds extracted — penicillin allergy is first-class." | SOAP note (allergy line) |
| **1:15** | "Warfarin on board — agent flags anticoagulation + chest pain." | Insights (high severity) |
| **1:30** | "Research pulls interaction references." | Insights (citations) |
| **1:45** | "GPS anchors the timeline — scene, contact, en route, arrival." | Timeline (telemetry) |
| **2:00** | Click **Scan scene** on aspirin vial (or let demo vision beat fire). | Insights (CV + warfarin flag) |
| **2:30** | "Nothing inferred from age alone — only stated facts cross-checked." | Insights rationale text |
| **3:00** | Click **Generate Handoff Report**. | Handoff modal |
| **3:30** | "Before: messy transcript. After: structured ED report with allergies, timeline, citations." | **Stop here** |

Do not end on an architecture slide.

---

## Beat-by-beat (matches `demo-scenario.json`)

Timing is **1 second between beats** in Demo Mode (~20s total).

| # | Time | Type | Speaker / event | Line or detail | Expected UI |
|---|------|------|-----------------|----------------|-------------|
| 0 | 0s | GPS | `scene_arrival` | Residential address, garden | Timeline: scene arrival |
| 1 | 1s | Transcript | Paramedic | "Ma'am, I'm Alex with county EMS. Can you tell me what happened?" | Transcript + timeline start |
| 2 | 2s | Transcript | Patient | "I've had chest pain for about two hours. It started suddenly while I was gardening." | Chief complaint extracted |
| 3 | 3s | Transcript | Paramedic | "Do you have any allergies to medications? Any current medications or medical history?" | — |
| 4 | 4s | Transcript | Patient | "I'm allergic to penicillin — I get a rash. I take lisinopril for my blood pressure." | **Allergies + lisinopril** in entities / SOAP |
| 5 | 5s | GPS | `patient_contact` | Seated on porch | Timeline anchor |
| 6 | 6s | Transcript | Paramedic | "Any blood thinners or heart medications?" | — |
| 7 | 7s | Transcript | Patient | "Yes, warfarin. I had a heart valve replacement three years ago." | **High safety flag** + research trigger |
| 8 | 8s | Transcript | Paramedic | Vitals: BP 158/94, HR 92, SpO2 96% | SOAP objective fills |
| 9 | 9s | Transcript | Paramedic | Supplemental O₂, 4L NC | Plan updates |
| 10 | 10s | Audio | `monitor_tone` | 12-lead ECG | Timeline: equipment event |
| 11 | 11s | Transcript | Paramedic | ECG sinus, SpO2 98%, documenting for hospital | — |
| 12 | 12s | Transcript | Paramedic | Loading patient, heading to County General | — |
| 13 | 13s | GPS | `en_route` | ETA 8 min | Timeline anchor |
| 14 | 14s | Transcript | Paramedic | SpO2 97%, keep mask on | — |
| 15 | 15s | Audio | `silence` | Quiet en route | Timeline: audio event |
| 16 | 16s | Transcript | Paramedic | Found medication bag at scene | — |
| 17 | 17s | Vision | `vial_label` | **Aspirin 325mg** | Vision on timeline; cross-check pending |
| 18 | 18s | Transcript | Paramedic | "I see an aspirin bottle. Were you taking aspirin regularly?" | — |
| 19 | 19s | Transcript | Patient | "No, just in the cabinet. Haven't taken any today." | — |
| 20 | 20s | GPS | `hospital_arrival` | County General ED bay 3 | Timeline anchor |

**After replay:** Click **Generate Handoff Report** — allergies prominent, GPS timeline, meds (spoken + vision), citations, outstanding questions.

---

## Demo trio (call out explicitly)

1. **Stated med + context** — Warfarin + chest pain → safety flag + Browserbase citations  
2. **CV cross-check** — Aspirin vial scan + patient on warfarin → flag before administration  
3. **Stated facts only** — Flags cite what was *said* or *scanned*, not age alone  

*(Missed follow-up timer uses real wall-clock time — may not fire during the 20s replay.)*

---

## Fallback lines if something breaks

- "Demo Mode uses the same agent pipeline as live mic — let me replay."  
- "In the field this camera is chest-mounted; we use a laptop cam for the hackathon."  
- "Allergy status travels in the handoff — that's what the ED needs first."

---

## Related files

- [demo-scenario.json](./demo-scenario.json) — injector source of truth  
- [DEMO_SCRIPT_B.md](./DEMO_SCRIPT_B.md) — alternate scenario (backup pitch)  
- [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md) — full product context  
