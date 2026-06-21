# Ambulance Copilot — Demo Script B (Alternate / Backup)

> **Status:** Presenter script only — not wired to `demo-scenario.json` yet.  
> Use if judges have already seen Script A, or you want a **trauma + unknown pills** angle.

Same product beats: allergies, stated-fact safety, CV scan, research, hospital handoff.

---

## Scenario summary

**Call type:** Fall from ladder at home improvement store parking lot  
**Patient:** 58M, conscious, wrist deformity, possible rib pain  
**Twist:** Bystander hands paramedic loose pills from patient's pocket; medical alert bracelet shows **sulfa allergy**; patient also mentions **metformin** for diabetes  

---

## One-liner

A paramedic can't memorize every pill imprint and every interaction en route — Ambulance Copilot identifies what was found on scene, cross-checks stated allergies and meds, and puts it all in the handoff.

---

## Dialogue (read aloud or adapt for live mic)

| Beat | Speaker | Line |
|------|---------|------|
| 1 | Paramedic | "Sir, I'm Jordan with EMS. You took a fall off that ladder — what hurts most right now?" |
| 2 | Patient | "My wrist. I think I landed on it. Ribs might be bruised." |
| 3 | Bystander | "He dropped these — they were in his jacket pocket." |
| 4 | Paramedic | "Any allergies? Medications? Last time you ate or drank?" |
| 5 | Patient | "Sulfa drugs — I swell up. I'm on metformin for diabetes. Last ate lunch around noon." |
| 6 | Paramedic | *(to partner)* "BP 142 over 88, pulse 88, pain 7 out of 10. Immobilize the wrist." |
| 7 | Paramedic | "I'm going to scan this bracelet and these pills before we give anything." |
| 8 | — | **[Scan scene]** Medical alert bracelet: `SULFA ALLERGY` |
| 9 | — | **[Scan scene]** Loose tablets: unidentified white oval (demo: label as unknown opioid-looking imprint) |
| 10 | Paramedic | "Do you take anything for pain at home? Oxycodone, tramadol, anything like that?" |
| 11 | Patient | "Sometimes tramadol for my back — not today though." |
| 12 | Paramedic | "Copy. Loading for General Hospital. ETA six minutes." |
| 13 | — | **[Generate Handoff Report]** |

---

## Expected agent behavior (when implemented)

| Trigger | Agent | Expected |
|---------|-------|----------|
| Sulfa allergy stated | Extraction | `allergies: ["sulfa"]` in entities |
| Metformin + tramadol stated | Extraction + Research | Citations on hypoglycemia / sedation in trauma |
| Bracelet scan confirms sulfa | Vision + Safety | Cross-check: do not give sulfonamide-class meds |
| Unknown pill scan | Vision + Research | Browserbase lookup on imprint; flag if high-risk |
| Last oral intake stated | NREMT | SAMPLE item covered — no reminder |
| Rib + wrist pain without reassessment | Safety (timer) | Remind to reassess pain / neuro after splinting |

---

## What to point at (pitch)

| Moment | Panel |
|--------|--------|
| Fall + wrist complaint | Transcript + timeline |
| Sulfa + metformin extracted | SOAP (allergies block) |
| Bracelet scan | Timeline (vision) + safety flag |
| Pill scan + research | Insights citations |
| Handoff | **Modal — stop here** |

---

## To wire this into Demo Mode

1. Copy structure from [demo-scenario.json](./demo-scenario.json)  
2. Replace beats with dialogue above (1s `delayMs` steps: 0, 1000, 2000, …)  
3. Add vision beats: `{ "type": "vision", "identified": "SULFA ALLERGY", "captureType": "bracelet" }`  
4. Tune extraction/safety prompts for sulfa + metformin + tramadol  
5. Rehearse once with **Demo** before judging  

---

## Related

- [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) — primary chest pain / warfarin script (live in JSON)  
- [ER_Copilot_Hackathon_Plan.md](../ER_Copilot_Hackathon_Plan.md) — product context  
