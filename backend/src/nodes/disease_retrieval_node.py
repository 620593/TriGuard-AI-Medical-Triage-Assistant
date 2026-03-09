"""
disease_retrieval_node.py  (Version 5 — Zero-Latency Local Lookup)
--------------------------------------------------------------------
Maps extracted symptoms to disease candidates using a fast in-memory
keyword dictionary — no network calls, no LLM, zero extra latency.

V5 changes:
    Previous version called Tavily API here AND in tavily_retrieval_node,
    causing DOUBLE the Tavily API calls on every text triage request.
    This version replaces the network call with a local symptom->disease
    keyword dict (O(n) lookup) to populate disease_candidates instantly.
    Tavily is called ONCE downstream in tavily_retrieval_node for grounded
    medical evidence.

    Result: eliminated one full Tavily round-trip (~300–800ms saved per request).
"""

import re

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("disease_retrieval")

# ── Local symptom → disease keyword mapping ──────────────────────────────────
# Covers the most common triage presentations. Fast O(n) scan, no network.
_SYMPTOM_DISEASE_MAP: dict[str, list[str]] = {
    "fever":          ["Viral infection", "Influenza", "Typhoid", "Malaria", "COVID-19"],
    "cough":          ["Common cold", "Bronchitis", "Pneumonia", "Tuberculosis", "COVID-19"],
    "headache":       ["Migraine", "Tension headache", "Hypertension", "Sinusitis", "Meningitis"],
    "chest pain":     ["Angina", "Myocardial infarction", "Costochondritis", "GERD", "Pulmonary embolism"],
    "shortness":      ["Asthma", "COPD", "Pneumonia", "Heart failure", "Pulmonary embolism"],
    "breath":         ["Asthma", "COPD", "Pneumonia", "Heart failure", "Pulmonary embolism"],
    "diarrhea":       ["Gastroenteritis", "IBS", "Food poisoning", "Salmonella", "Cholera"],
    "loose motion":   ["Gastroenteritis", "IBS", "Food poisoning", "Cholera", "Traveler's diarrhea"],
    "loose":          ["Gastroenteritis", "IBS", "Food poisoning", "Cholera"],
    "vomit":          ["Gastroenteritis", "Food poisoning", "Appendicitis", "Migraine", "Pregnancy"],
    "nausea":         ["Gastroenteritis", "GERD", "Migraine", "Pregnancy", "Food poisoning"],
    "stomach":        ["Gastritis", "Appendicitis", "IBS", "Food poisoning", "GERD"],
    "abdominal":      ["Appendicitis", "IBS", "GERD", "Pancreatitis", "Hernia"],
    "fatigue":        ["Anemia", "Hypothyroidism", "Diabetes", "Depression", "COVID-19"],
    "rash":           ["Allergic reaction", "Eczema", "Psoriasis", "Chickenpox", "Measles"],
    "joint":          ["Arthritis", "Gout", "Lupus", "Rheumatoid arthritis", "Lyme disease"],
    "back pain":      ["Lumbar strain", "Herniated disc", "Sciatica", "Kidney stones", "Osteoporosis"],
    "sore throat":    ["Pharyngitis", "Tonsillitis", "Strep throat", "Mono", "COVID-19"],
    "runny nose":     ["Common cold", "Allergic rhinitis", "Influenza", "Sinusitis"],
    "dizziness":      ["Vertigo", "Anemia", "Hypotension", "Dehydration", "Inner ear disorder"],
    "swelling":       ["Edema", "Cellulitis", "DVT", "Heart failure", "Lymphedema"],
    "fracture":       ["Bone fracture", "Stress fracture", "Osteoporosis-related fracture"],
    "broken":         ["Bone fracture", "Trauma", "Stress fracture"],
    "diabetes":       ["Type 2 Diabetes", "Type 1 Diabetes", "Pre-diabetes"],
    "blood pressure": ["Hypertension", "Hypotension", "Cardiovascular disease"],
    "eye":            ["Conjunctivitis", "Glaucoma", "Uveitis", "Dry eye syndrome"],
    "ear":            ["Otitis media", "Ear infection", "Tinnitus", "Hearing loss"],
    "urination":      ["UTI", "Diabetes", "Prostatitis", "Kidney infection"],
    "burn":           ["Burn injury", "Chemical burn", "Sunburn"],
    "bleeding":       ["Hemorrhage", "Anemia", "Clotting disorder", "Trauma"],
    "anxiety":        ["Anxiety disorder", "Panic disorder", "PTSD", "Generalized anxiety"],
    "depression":     ["Major depressive disorder", "Bipolar disorder", "Dysthymia"],
    "insomnia":       ["Sleep disorder", "Anxiety", "Depression", "Sleep apnea"],
}

# Precompile a regex to match any of the keywords for fast multiple substring search.
# Keys are sorted by length descending so that longer overlapping keywords (e.g. "loose motion")
# match before their shorter substrings ("loose").
_SORTED_KEYWORDS = sorted(_SYMPTOM_DISEASE_MAP.keys(), key=len, reverse=True)
_SYMPTOM_PATTERN = re.compile('|'.join(re.escape(k) for k in _SORTED_KEYWORDS))


async def disease_retrieval_node(state: TriageState) -> TriageState:
    """
    Maps extracted symptoms to likely disease candidates using a fast local lookup.

    Args:
        state: Contains symptoms list.

    Returns:
        TriageState: With disease_candidates populated (no network I/O).
    """
    symptoms = state.get("symptoms", [])

    if not symptoms:
        state["disease_candidates"] = []
        log_event(logger, "disease_retrieval_skipped", reason="no_symptoms")
        return state

    # Build candidate set via regex search (O(n) scan per symptom, very fast)
    candidates: list[str] = []
    seen: set[str] = set()

    for symptom in symptoms:
        symptom_lower = symptom.lower()
        for match in _SYMPTOM_PATTERN.finditer(symptom_lower):
            keyword = match.group()
            for disease in _SYMPTOM_DISEASE_MAP[keyword]:
                if disease not in seen:
                    seen.add(disease)
                    candidates.append(disease)

    # Cap to top 6 candidates to keep downstream prompts lean
    state["disease_candidates"] = candidates[:6]

    log_event(logger, "disease_retrieval_complete",
              symptom_count=len(symptoms),
              candidates_found=len(state["disease_candidates"]),
              source="local_lookup")

    return state
