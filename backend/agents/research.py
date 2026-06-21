"""
Research agent — mirrors lib/agents/research.ts.
Fetches PubMed citations + mock guideline data on new medications/allergies.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import httpx

from browserbase import browserbase_search, has_browserbase
from bus import InMemoryBus, RedisBus
from events import EVENT_CHANNELS, Citation, MedicalEntities, entities_from_dict, to_dict
from redis_layer.keys import EncounterKeys
from redis_layer.state import add_to_set, load_json, save_json

logger = logging.getLogger(__name__)

# ─── Curated mock citations per medication ─────────────────────────────────────

_MockEntry = Dict[str, object]

MOCK_CITATIONS: Dict[str, _MockEntry] = {
    "warfarin": {
        "findings": (
            "Warfarin-treated patients presenting with ACS require careful balance of antithrombotic "
            "therapy. Current guidelines recommend risk-stratified management weighing hemorrhagic vs. "
            "thrombotic risk. INR monitoring is critical before initiating additional antiplatelet agents."
        ),
        "citations": [
            Citation(
                title="2023 ACC/AHA Guideline for Diagnosis and Management of Acute Coronary Syndromes",
                url="https://www.acc.org/clinical-topics/acute-coronary-syndrome",
                snippet="For patients on oral anticoagulation presenting with ACS, individualized decision-making is required for antiplatelet co-therapy.",
            ),
            Citation(
                title="Warfarin Drug Interactions — FDA Prescribing Information",
                url="https://www.accessdata.fda.gov/drugsatfda_docs/label/2011/009218s108lbl.pdf",
                snippet="Increased bleeding risk with concurrent antiplatelet agents. Monitor INR closely when aspirin is co-administered.",
            ),
            Citation(
                title="Triple Therapy in ACS: Balancing Stroke Prevention and Bleeding Risk (NEJM)",
                url="https://pubmed.ncbi.nlm.nih.gov/?term=warfarin+ACS+antiplatelet+triple+therapy",
                snippet="Dual therapy (OAC + single antiplatelet) preferred over triple therapy to reduce major bleeding without increasing thrombotic events.",
            ),
        ],
    },
    "lisinopril": {
        "findings": (
            "ACE inhibitors (lisinopril) are first-line for hypertension with cardiovascular comorbidities. "
            "In ACS, ACE inhibitors reduce mortality. Long-term therapy is beneficial in patients with LV dysfunction."
        ),
        "citations": [
            Citation(
                title="JNC 8 — Evidence-Based Guideline for Management of High Blood Pressure",
                url="https://pubmed.ncbi.nlm.nih.gov/24352797/",
                snippet="ACE inhibitors or ARBs are recommended first-line in patients with CKD or diabetes. Strong evidence for cardiovascular risk reduction.",
            ),
            Citation(
                title="GISSI-3 Trial: Lisinopril in Acute MI — Lancet",
                url="https://pubmed.ncbi.nlm.nih.gov/7661937/",
                snippet="Lisinopril reduced 6-week mortality in patients with acute MI when initiated within 24 hours of symptom onset.",
            ),
        ],
    },
    "aspirin": {
        "findings": (
            "Aspirin 162–325 mg is standard of care for ACS unless contraindicated. In anticoagulated "
            "patients (warfarin), dual antithrombotic therapy significantly increases bleeding risk and "
            "should be carefully considered."
        ),
        "citations": [
            Citation(
                title="ASPREE Trial: Effect of Aspirin in Older Adults — NEJM 2018",
                url="https://pubmed.ncbi.nlm.nih.gov/30152129/",
                snippet="Aspirin did not significantly reduce disability-free survival but increased major hemorrhage risk in healthy older adults.",
            ),
            Citation(
                title="Antiplatelet Therapy in ACS — ACC/AHA 2023 Clinical Performance Measures",
                url="https://www.acc.org/latest-in-cardiology/articles/2023/07/aspirin-acs",
                snippet="Aspirin remains cornerstone of ACS treatment. Consider bleeding risk before combining with anticoagulation.",
            ),
        ],
    },
}

ALLERGY_CITATIONS: Dict[str, _MockEntry] = {
    "penicillin": {
        "findings": (
            "Documented penicillin allergy is present. Cross-reactivity with cephalosporins is "
            "approximately 1–2%. Azithromycin, clindamycin, or vancomycin may be used as alternatives "
            "depending on indication."
        ),
        "citations": [
            Citation(
                title="Penicillin Allergy: A Practical Guide for Clinicians — Mayo Clinic Proc.",
                url="https://pubmed.ncbi.nlm.nih.gov/28888634/",
                snippet="Up to 80% of patients labeled as penicillin-allergic can tolerate penicillin. Cross-reactivity with cephalosporins is ~1–2%.",
            ),
        ],
    },
}


# ─── PubMed E-utilities ─────────────────────────────────────────────────────────

async def pubmed_search(drug: str, context: str) -> Optional[List[Citation]]:
    try:
        query = f"{drug} {context} guidelines"
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        async with httpx.AsyncClient(timeout=4.0) as client:
            search_resp = await client.get(
                f"{base}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": 3, "retmode": "json", "sort": "relevance"},
            )
            if not search_resp.is_success:
                return None
            search_data = search_resp.json()
            ids = search_data.get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None

            summary_resp = await client.get(
                f"{base}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
            )
            if not summary_resp.is_success:
                return None
            result = summary_resp.json().get("result", {})

            citations = []
            for id_ in ids:
                entry = result.get(id_, {})
                if not entry.get("title"):
                    continue
                authors = entry.get("authors", [])
                author_str = ", ".join(a.get("name", "") for a in authors[:3])
                year = str(entry.get("pubdate", ""))[:4]
                source = entry.get("source", "PubMed")
                citations.append(Citation(
                    title=f"{entry['title']} ({source}, {year})",
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{id_}/",
                    snippet=author_str,
                ))
            return citations if citations else None
    except Exception as e:
        logger.debug("[research] pubmed search failed: %s", e)
        return None


# ─── Agent ─────────────────────────────────────────────────────────────────────

async def start_research_agent(bus: InMemoryBus | RedisBus) -> Callable[[], None]:
    async def on_facts_extracted(envelope: dict) -> None:
        payload = envelope.get("payload", {})
        encounter_id = payload.get("encounterId", "")
        entities = entities_from_dict(payload.get("entities", {}))

        await _research_medications(bus, encounter_id, entities)
        await _research_allergies(bus, encounter_id, entities)

    return await bus.subscribe(EVENT_CHANNELS.FACTS_EXTRACTED, on_facts_extracted)


async def _research_medications(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    entities: MedicalEntities,
) -> None:
    for med in entities.medications:
        key = med.name.lower()
        is_new = await add_to_set(EncounterKeys.researched_meds(encounter_id), key)
        if not is_new:
            continue

        context = (
            "chest pain ACS"
            if any("chest pain" in s for s in entities.symptoms)
            else "cardiovascular"
        )

        mock = MOCK_CITATIONS.get(key)

        # Source priority: live Browserbase (when keyed) → PubMed → curated mock.
        bb_cites = (
            await browserbase_search(f"{med.name} {context} drug interaction guideline")
            if has_browserbase()
            else None
        )

        if bb_cites:
            mock_cites: List[Citation] = list(mock["citations"])[:1] if mock else []  # type: ignore[index]
            citations = mock_cites + bb_cites[:2]
            findings = str(mock["findings"]) if mock else (  # type: ignore[index]
                f"{med.name}: Live web review via Browserbase. See citations for drug "
                "interactions and dosing guidance relevant to the current presentation."
            )
        else:
            pubmed_cites = await pubmed_search(med.name, context)
            if pubmed_cites:
                mock_cites = list(mock["citations"])[:1] if mock else []  # type: ignore[index]
                citations = mock_cites + pubmed_cites[:2]
                findings = str(mock["findings"]) if mock else (  # type: ignore[index]
                    f"{med.name}: Clinical evidence reviewed. See citations for drug interactions "
                    "and dosing guidelines relevant to the current presentation."
                )
            else:
                citations = list(mock["citations"]) if mock else [  # type: ignore[index]
                    Citation(
                        title=f"{med.name} — PubMed Search",
                        url=f"https://pubmed.ncbi.nlm.nih.gov/?term={med.name.replace(' ', '+')}+guidelines",
                        snippet=f"Search results for {med.name} clinical guidelines.",
                    )
                ]
                findings = str(mock["findings"]) if mock else (  # type: ignore[index]
                    f"{med.name}: Review contraindications and interactions relevant to current presentation."
                )

        payload = {
            "encounterId": encounter_id,
            "query": f"{med.name} {context}",
            "findings": findings,
            "citations": [to_dict(c) for c in citations],
            "completedAt": datetime.now(timezone.utc).isoformat(),
        }

        prior = await load_json(EncounterKeys.research(encounter_id)) or []
        await save_json(EncounterKeys.research(encounter_id), prior + [payload])
        await bus.publish(EVENT_CHANNELS.RESEARCH_COMPLETED, payload)


async def _research_allergies(
    bus: InMemoryBus | RedisBus,
    encounter_id: str,
    entities: MedicalEntities,
) -> None:
    for allergy in entities.allergies:
        key = f"allergy:{allergy.lower()}"
        is_new = await add_to_set(EncounterKeys.researched_meds(encounter_id), key)
        if not is_new:
            continue

        allergy_key = allergy.lower().replace(" allergy", "").strip()
        allergy_data = ALLERGY_CITATIONS.get(allergy_key)

        payload = {
            "encounterId": encounter_id,
            "query": f"{allergy} management",
            "findings": str(allergy_data["findings"]) if allergy_data else (  # type: ignore[index]
                f"{allergy} allergy documented. Verify all ordered medications for cross-reactivity."
            ),
            "citations": [to_dict(c) for c in allergy_data["citations"]] if allergy_data else [],  # type: ignore[index]
            "completedAt": datetime.now(timezone.utc).isoformat(),
        }

        await bus.publish(EVENT_CHANNELS.RESEARCH_COMPLETED, payload)
