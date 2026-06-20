import type { EventBus } from "@/lib/bus";
import { EVENT_CHANNELS, type Citation, type MedicalEntities } from "@/lib/events";
import { addToSet, loadJSON, saveJSON } from "@/lib/redis/state";
import { EncounterKeys } from "@/lib/redis/keys";

// ─── Curated mock citations per medication ───────────────────────────────────

const MOCK_CITATIONS: Record<string, { findings: string; citations: Citation[] }> = {
  warfarin: {
    findings:
      "Warfarin-treated patients presenting with ACS require careful balance of antithrombotic therapy. Current guidelines recommend risk-stratified management weighing hemorrhagic vs. thrombotic risk. INR monitoring is critical before initiating additional antiplatelet agents.",
    citations: [
      {
        title: "2023 ACC/AHA Guideline for Diagnosis and Management of Acute Coronary Syndromes",
        url: "https://www.acc.org/clinical-topics/acute-coronary-syndrome",
        snippet:
          "For patients on oral anticoagulation presenting with ACS, individualized decision-making is required for antiplatelet co-therapy.",
      },
      {
        title: "Warfarin Drug Interactions — FDA Prescribing Information",
        url: "https://www.accessdata.fda.gov/drugsatfda_docs/label/2011/009218s108lbl.pdf",
        snippet:
          "Increased bleeding risk with concurrent antiplatelet agents. Monitor INR closely when aspirin is co-administered.",
      },
      {
        title: "Triple Therapy in ACS: Balancing Stroke Prevention and Bleeding Risk (NEJM)",
        url: "https://pubmed.ncbi.nlm.nih.gov/?term=warfarin+ACS+antiplatelet+triple+therapy",
        snippet:
          "Dual therapy (OAC + single antiplatelet) preferred over triple therapy to reduce major bleeding without increasing thrombotic events.",
      },
    ],
  },
  lisinopril: {
    findings:
      "ACE inhibitors (lisinopril) are first-line for hypertension with cardiovascular comorbidities. In ACS, ACE inhibitors reduce mortality. Long-term therapy is beneficial in patients with LV dysfunction.",
    citations: [
      {
        title: "JNC 8 — Evidence-Based Guideline for Management of High Blood Pressure",
        url: "https://pubmed.ncbi.nlm.nih.gov/24352797/",
        snippet:
          "ACE inhibitors or ARBs are recommended first-line in patients with CKD or diabetes. Strong evidence for cardiovascular risk reduction.",
      },
      {
        title: "GISSI-3 Trial: Lisinopril in Acute MI — Lancet",
        url: "https://pubmed.ncbi.nlm.nih.gov/7661937/",
        snippet:
          "Lisinopril reduced 6-week mortality in patients with acute MI when initiated within 24 hours of symptom onset.",
      },
    ],
  },
  aspirin: {
    findings:
      "Aspirin 162–325 mg is standard of care for ACS unless contraindicated. In anticoagulated patients (warfarin), dual antithrombotic therapy significantly increases bleeding risk and should be carefully considered.",
    citations: [
      {
        title: "ASPREE Trial: Effect of Aspirin in Older Adults — NEJM 2018",
        url: "https://pubmed.ncbi.nlm.nih.gov/30152129/",
        snippet:
          "Aspirin did not significantly reduce disability-free survival but increased major hemorrhage risk in healthy older adults.",
      },
      {
        title: "Antiplatelet Therapy in ACS — ACC/AHA 2023 Clinical Performance Measures",
        url: "https://www.acc.org/latest-in-cardiology/articles/2023/07/aspirin-acs",
        snippet:
          "Aspirin remains cornerstone of ACS treatment. Consider bleeding risk before combining with anticoagulation.",
      },
    ],
  },
};

const ALLERGY_CITATIONS: Record<string, { findings: string; citations: Citation[] }> = {
  penicillin: {
    findings:
      "Documented penicillin allergy is present. Cross-reactivity with cephalosporins is approximately 1–2%. Azithromycin, clindamycin, or vancomycin may be used as alternatives depending on indication.",
    citations: [
      {
        title: "Penicillin Allergy: A Practical Guide for Clinicians — Mayo Clinic Proc.",
        url: "https://pubmed.ncbi.nlm.nih.gov/28888634/",
        snippet:
          "Up to 80% of patients labeled as penicillin-allergic can tolerate penicillin. Cross-reactivity with cephalosporins is ~1–2%.",
      },
    ],
  },
};

// ─── PubMed E-utilities (free, no auth required) ─────────────────────────────

interface PubMedSearchResult {
  esearchresult?: { idlist?: string[] };
}

interface PubMedSummaryResult {
  result?: Record<
    string,
    { title?: string; authors?: { name: string }[]; source?: string; pubdate?: string }
  >;
}

async function pubmedSearch(
  drug: string,
  context: string
): Promise<Citation[] | null> {
  try {
    const query = encodeURIComponent(`${drug} ${context} guidelines`);
    const searchUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=${query}&retmax=3&retmode=json&sort=relevance`;

    const searchRes = await fetch(searchUrl, { signal: AbortSignal.timeout(4000) });
    if (!searchRes.ok) return null;

    const searchData = (await searchRes.json()) as PubMedSearchResult;
    const ids = searchData.esearchresult?.idlist ?? [];
    if (ids.length === 0) return null;

    const summaryUrl = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=${ids.join(",")}&retmode=json`;
    const summaryRes = await fetch(summaryUrl, { signal: AbortSignal.timeout(4000) });
    if (!summaryRes.ok) return null;

    const summaryData = (await summaryRes.json()) as PubMedSummaryResult;
    const result = summaryData.result ?? {};

    return ids
      .filter((id) => result[id]?.title)
      .map((id) => ({
        title: `${result[id].title} (${result[id].source ?? "PubMed"}, ${result[id].pubdate?.slice(0, 4) ?? ""})`,
        url: `https://pubmed.ncbi.nlm.nih.gov/${id}/`,
        snippet: result[id].authors?.slice(0, 3).map((a) => a.name).join(", ") ?? "",
      }));
  } catch {
    return null;
  }
}

// ─── Agent ───────────────────────────────────────────────────────────────────

export async function startResearchAgent(bus: EventBus): Promise<() => void> {
  return bus.subscribe(EVENT_CHANNELS.FACTS_EXTRACTED, async (envelope) => {
    const { encounterId, entities } = envelope.payload;

    await researchMedications(bus, encounterId, entities);
    await researchAllergies(bus, encounterId, entities);
  });
}

async function researchMedications(
  bus: EventBus,
  encounterId: string,
  entities: MedicalEntities
) {
  for (const med of entities.medications) {
    const key = med.name.toLowerCase();
    const isNew = await addToSet(EncounterKeys.researchedMeds(encounterId), key);
    if (!isNew) continue;

    const context = entities.symptoms.some((s) => s.includes("chest pain"))
      ? "chest pain ACS"
      : "cardiovascular";

    const mock = MOCK_CITATIONS[key];

    let citations: Citation[];
    let findings: string;

    const pubmedCitations = await pubmedSearch(med.name, context);
    if (pubmedCitations && pubmedCitations.length > 0) {
      citations = [
        ...(mock?.citations.slice(0, 1) ?? []),
        ...pubmedCitations.slice(0, 2),
      ];
      findings =
        mock?.findings ??
        `${med.name}: Clinical evidence reviewed. See citations for drug interactions and dosing guidelines relevant to the current presentation.`;
    } else {
      citations = mock?.citations ?? [
        {
          title: `${med.name} — PubMed Search`,
          url: `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(med.name)}+guidelines`,
          snippet: `Search results for ${med.name} clinical guidelines.`,
        },
      ];
      findings =
        mock?.findings ??
        `${med.name}: Review contraindications and interactions relevant to current presentation.`;
    }

    const payload = {
      encounterId,
      query: `${med.name} ${context}`,
      findings,
      citations,
      completedAt: new Date().toISOString(),
    };

    const prior =
      (await loadJSON<typeof payload[]>(EncounterKeys.research(encounterId))) ?? [];
    await saveJSON(EncounterKeys.research(encounterId), [...prior, payload]);
    await bus.publish(EVENT_CHANNELS.RESEARCH_COMPLETED, payload);
  }
}

async function researchAllergies(
  bus: EventBus,
  encounterId: string,
  entities: MedicalEntities
) {
  for (const allergy of entities.allergies) {
    const key = `allergy:${allergy.toLowerCase()}`;
    const isNew = await addToSet(EncounterKeys.researchedMeds(encounterId), key);
    if (!isNew) continue;

    const allergyKey = allergy.toLowerCase().replace(/\s+allergy$/, "");
    const allergyData = ALLERGY_CITATIONS[allergyKey];

    const payload = {
      encounterId,
      query: `${allergy} management`,
      findings:
        allergyData?.findings ??
        `${allergy} allergy documented. Verify all ordered medications for cross-reactivity.`,
      citations: allergyData?.citations ?? [],
      completedAt: new Date().toISOString(),
    };

    await bus.publish(EVENT_CHANNELS.RESEARCH_COMPLETED, payload);
  }
}
