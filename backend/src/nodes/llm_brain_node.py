"""
llm_brain_node.py  (Version 7 — Production Hardened)
-----------------------------------------
Generates a STRICT structured JSON triage response using Groq LLaMA.

V7 changes:
    - FIX #4: Detects distress words → prepends calming prefix to clinical_summary.
    - FIX #5: Risk-calibrated tone rule in prompt (LOW calm / MODERATE suggest doc / HIGH urgent-not-scary).
    - FIX #7: FORBIDDEN diagnosis language in prompt + alternate phrasing required.
    - FIX #8: Max chars 800 for low/moderate, 1200 for high/critical.
    - FIX #8: Confidence < 0.6 → shorten + add "This is based on limited information."

V6 contract (preserved):
    - Input:  state["reasoning_input"] (from context_synthesizer_node)
    - Output: state["llm_output"] — strict JSON dict
    - No formatting. No presentation. No disclaimers. Reasoning only.
"""

import json
import asyncio

from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.utils.fallback_responses import vision_error_response, empty_input_response

logger = get_logger("llm_brain")

_RISK_LEVELS = frozenset({"low", "moderate", "high", "critical", "unknown"})
_URGENCY_LEVELS = frozenset({"routine", "urgent", "emergency", "critical"})

# FIX #4 — Distress trigger words
_DISTRESS_WORDS = frozenset({"afraid", "scared", "worry", "worried", "panic", "terrified", "panicking"})


def _fallback_llm_output(reason: str, risk_level: str, urgency: str) -> dict:
    return {
        "clinical_summary":   f"Assessment unavailable: {reason}",
        "possible_causes":    [],
        "risk_level":         risk_level,
        "recommended_action": "Please describe your symptoms or consult a healthcare provider.",
        "urgency":            urgency,
        "confidence_score":   0.0,
        "suggested_otc":      None,
        "nutrition_tip":      None,
    }


def _parse_llm_output(raw: str, fallback_risk: str, fallback_urgency: str, max_summary_len: int = 800) -> dict:
    """Parses strict JSON from LLM output. Falls back to safe defaults on failure."""
    raw = raw.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON block from text
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except json.JSONDecodeError:
                return _fallback_llm_output("JSON parse failure", fallback_risk, fallback_urgency)
        else:
            return _fallback_llm_output("No JSON in response", fallback_risk, fallback_urgency)

    # Validate and sanitize fields
    return {
        "clinical_summary":   str(parsed.get("clinical_summary", ""))[:max_summary_len],
        "possible_causes":    [str(c) for c in parsed.get("possible_causes", [])][:5],
        "risk_level":         parsed.get("risk_level", fallback_risk).lower()
                              if parsed.get("risk_level", "").lower() in _RISK_LEVELS
                              else fallback_risk,
        "recommended_action": str(parsed.get("recommended_action", ""))[:600],
        "urgency":            parsed.get("urgency", fallback_urgency).lower()
                              if parsed.get("urgency", "").lower() in _URGENCY_LEVELS
                              else fallback_urgency,
        "confidence_score":   min(1.0, max(0.0, float(parsed.get("confidence_score", 0.5)))),
        "suggested_otc":      parsed.get("suggested_otc"),
        "nutrition_tip":      parsed.get("nutrition_tip"),
    }


def _build_reasoning_fallback(state: TriageState) -> str:
    """Builds minimal reasoning context from structured state when synthesizer input is absent."""
    parts = []

    user_input = (state.get("user_input", "") or "").strip()
    if user_input:
        parts.append(f"User input: {user_input}")

    symptoms = [str(item).strip() for item in state.get("symptoms", []) if str(item).strip()]
    if symptoms:
        parts.append(f"Symptoms: {', '.join(symptoms)}")

    retrieved_info = [str(item).strip() for item in state.get("retrieved_info", []) if str(item).strip()]
    if retrieved_info:
        parts.append(f"Retrieved context: {' '.join(retrieved_info[:3])}")

    vision_findings = state.get("vision_findings") or {}
    if vision_findings:
        visual_items = vision_findings.get("visual_findings") or []
        explanation = str(vision_findings.get("explanation", "")).strip()
        if visual_items:
            parts.append(f"Visual findings: {', '.join(str(item) for item in visual_items[:5])}")
        if explanation:
            parts.append(f"Vision explanation: {explanation}")

    nutrition_advice = (state.get("nutrition_advice", "") or "").strip()
    if nutrition_advice:
        parts.append(f"Nutrition advice: {nutrition_advice}")

    return "\n".join(parts)


async def llm_brain_node(state: TriageState) -> TriageState:
    """
    Generates structured {clinical_summary, possible_causes, risk_level,
    recommended_action, urgency, confidence_score} via LLaMA.

    No formatting, no presentation, no disclaimers — reasoning only.

    Args:
        state: Contains reasoning_input, risk_level, urgency, symptoms.

    Returns:
        TriageState: llm_output populated; last_structured_summary/risk/intent updated.
    """
    risk_level = state.get("risk_level", "unknown")
    urgency    = state.get("urgency", "routine")

    # ── Fast-exit: deterministic emergency interrupt ────────────────────────
    if state.get("next_action") == "priority_interrupt":
        symptoms = ", ".join(state.get("symptoms", [])[:3]) or "severe symptoms"
        if state.get("mental_health_flag"):
            emergency_message = (
                "This sounds like a mental health emergency. Please call or text 988 now, "
                "or go to the nearest emergency department immediately if you may act on these thoughts. "
                "Stay with a trusted person and do not remain alone."
            )
        else:
            emergency_message = (
                f"This may be a medical emergency involving {symptoms}. "
                "Call emergency services now or go to the nearest emergency room immediately. "
                "Do not wait for symptoms to settle on their own."
            )

        state["llm_output"] = {
            "clinical_summary": emergency_message,
            "possible_causes": [],
            "risk_level": risk_level,
            "recommended_action": emergency_message,
            "urgency": urgency if urgency in _URGENCY_LEVELS else "emergency",
            "confidence_score": max(float(state.get("risk_confidence", 0.0) or 0.0), 0.95),
            "suggested_otc": None,
            "nutrition_tip": None,
        }
        state["last_structured_summary"] = emergency_message[:600]
        state["last_risk_level"] = risk_level
        state["last_intent"] = state.get("intent", "medical_text") or "medical_text"
        state["messages"] = state.get("messages", []) + [
            {"role": "assistant", "content": emergency_message}
        ]
        log_event(logger, "llm_brain_priority_interrupt", risk_level=risk_level, urgency=urgency)
        return state

    # ── Fast-exit: vision API failed ─────────────────────────────────────────
    if state.get("vision_error"):
        msg = vision_error_response()
        state["messages"] = state.get("messages", []) + [{"role": "assistant", "content": msg}]
        state["llm_output"] = _fallback_llm_output("vision_error", risk_level, urgency)
        state["fallback_used"] = True
        log_event(logger, "llm_brain_vision_error_exit", risk_level=risk_level)
        return state

    # ── Fast-exit: X-ray handled upstream ────────────────────────────────────
    if state.get("xray_findings"):
        xray_text = str(state.get("xray_findings", ""))
        state["llm_output"] = {
            "clinical_summary":   xray_text[:800],
            "possible_causes":    [],
            "risk_level":         risk_level,
            "recommended_action": "Consult a radiologist for full interpretation.",
            "urgency":            urgency,
            "confidence_score":   0.7,
            "suggested_otc":      None,
            "nutrition_tip":      None,
        }
        # Store for cross-turn context
        state["last_structured_summary"] = xray_text[:600]
        state["last_risk_level"]         = risk_level
        state["last_intent"]             = "xray"
        log_event(logger, "llm_brain_xray_passthrough")
        return state

    # ── Fast-exit: low-confidence vision result ──────────────────────────────
    vision_findings = state.get("vision_findings") or {}
    vision_confidence = float(vision_findings.get("confidence", 0.0) or 0.0)
    if vision_findings and vision_confidence < 0.6:
        msg = (
            "The image is not clear enough for a safe assessment. "
            "Please upload a clearer image with better lighting and focus, "
            "or describe what you are seeing in text."
        )
        state["messages"] = state.get("messages", []) + [{"role": "assistant", "content": msg}]
        state["llm_output"] = _fallback_llm_output("low_vision_confidence", risk_level, urgency)
        state["fallback_used"] = True
        log_event(logger, "llm_brain_low_confidence_vision_exit", confidence=vision_confidence)
        return state

    # ── Get reasoning input ───────────────────────────────────────────────────
    reasoning_input = (state.get("reasoning_input", "") or "").strip()
    if not reasoning_input:
        reasoning_input = _build_reasoning_fallback(state)
        if reasoning_input:
            state["reasoning_input"] = reasoning_input

    if not reasoning_input:
        state["llm_output"] = _fallback_llm_output(
            "no_reasoning_input", risk_level, urgency
        )
        state["fallback_used"] = True
        msg = empty_input_response(risk_level)
        state["messages"] = state.get("messages", []) + [{"role": "assistant", "content": msg}]
        log_event(logger, "llm_brain_empty_input_exit", risk_level=risk_level)
        return state

    # ── Detect Medication Request ────────────────────────────────────────────
    user_input = state.get("user_input", "").lower()
    med_keywords = ["medicine", "medication", "tablet", "drug", "take for", "suggest medicine", "what should i take", "dolo", "syrup"]
    if any(kw in user_input for kw in med_keywords):
        state["medication_requested"] = True
    else:
        state["medication_requested"] = False

    # ── Build language instruction ────────────────────────────────────────────
    language = state.get("language", "en")
    lang_instruction = (
        f"Respond in {language} language for the 'clinical_summary' and "
        f"'recommended_action' fields only. All JSON keys must stay in English.\n"
        if language != "en"
        else ""
    )

    # Use one consistent response structure for text, OCR, and body-image turns.
    summary_instruction = (
        '  "clinical_summary": "<3-5 sentence plain-language summary. '
        'Directly address the symptoms using provided medical context. '
        'Be helpful but never give a definitive diagnosis. Use cautious phrasing.>",')
    action_instruction = (
        '  "recommended_action": "<Clear, specific next steps or actionable advice>",')
    max_tokens  = 800

    # ── OTC approved list ─────────────────────────────────────────────────────
    APPROVED_OTC_LIST = (
        "Fever/Pain: Paracetamol 500mg (Dolo 650), Ibuprofen 400mg\n"
        "Cold/Flu: Cetirizine 10mg (Cetzine), Levocetirizine 5mg\n"
        "Cough: Dextromethorphan syrup, Honey + ginger (home remedy)\n"
        "Acidity: Pantoprazole 40mg, Gelusil/Digene syrup\n"
        "Motions/Loose: ORS sachets, Loperamide 2mg (Imodium), Metronidazole 400mg\n"
        "Nausea: Domperidone 10mg (Domstal), Ondansetron 4mg (Emeset)\n"
        "Headache: Paracetamol 650mg, Aspirin 325mg (not for children)\n"
        "Allergies: Cetirizine 10mg, Chlorpheniramine 4mg\n"
        "Vitamins: Vitamin C, Vitamin D3, B-complex, Zinc"
    )

    med_instruction = ""
    if state.get("medication_requested"):
        med_instruction = (
            "If medication_requested=True AND risk is low/moderate:\n"
            "suggest ONLY from the approved OTC list below.\n"
            "Include medicine name, dosage, and when to take.\n"
            "If the symptom is not covered by the OTC list, say 'consult a pharmacist' — never guess.\n"
            f"APPROVED OTC LIST:\n{APPROVED_OTC_LIST}\n"
        )

    # ── FIX #4 — Emotional intelligence: detect distress words ───────────────
    user_text_lower = (state.get("user_input", "") + " " + reasoning_input).lower()
    calming_prefix = ""
    if any(word in user_text_lower for word in _DISTRESS_WORDS):
        calming_prefix = "I understand this can feel worrying. Let\u2019s go step by step.\n\n"

    # ── FIX #5 — Risk-calibrated tone instruction ─────────────────────────────
    risk_tone_rule = (
        "TONE RULE (MANDATORY):\n"
        "- LOW risk: Be calm and reassuring. Never alarm the user.\n"
        "- MODERATE risk: Calmly suggest seeing a doctor. No scary language.\n"
        "- HIGH/CRITICAL risk: Be clear and direct, but NOT panic-inducing.\n"
    )

    # ── FIX #8 — Response length based on risk ────────────────────────────────
    if risk_level in ("low", "moderate"):
        max_summary_chars = 800
    else:
        max_summary_chars = 1200

    # ── FIX #7 — Language rule with forbidden diagnosis patterns ─────────────
    simple_english_rule = (
        "LANGUAGE RULE \u2014 MANDATORY:\n"
        "Write ALL responses in simple, friendly English that a 10-year-old can understand.\n"
        "- Never use medical jargon (replace: pharyngitis \u2192 throat infection, pyrexia \u2192 fever, "
        "myalgia \u2192 muscle pain, dyspnea \u2192 difficulty breathing, hypertension \u2192 high blood pressure, "
        "tachycardia \u2192 fast heartbeat, edema \u2192 swelling, prognosis \u2192 how things will go, "
        "acute \u2192 sudden/severe, chronic \u2192 long-lasting).\n"
        "- Use short sentences. Maximum 15 words per sentence.\n"
        "- Use 'you' and 'your' \u2014 talk directly to the patient.\n"
        "- CRITICAL #7: NEVER say 'You have [disease]', 'This is [disease]', "
        "'It looks like you have [X]'. ALWAYS use: 'This could be due to...', "
        "'Possible causes include...', 'Based on what you\u2019ve told me...'\n"
        "- Start clinical_summary with 'Based on what you\u2019ve told me...' or 'Possible causes include...'\n"
        "- Start recommended_action with 'You should...' or 'Please...'\n"
    )

    # ── Build full prompt ─────────────────────────────────────────────────────
    prompt = (
        "You are TriGuard AI, a conservative medical triage reasoning engine.\n"
        f"{lang_instruction}"
        f"{simple_english_rule}\n"
        f"{risk_tone_rule}\n"
        "RULES:\n"
        "- NEVER diagnose or prescribe medications (except as explicitly allowed below).\n"
        "- NEVER invent symptoms not mentioned by the patient or not visible in the image.\n"
        "- ALWAYS use cautious phrasing: 'possible causes include', 'this could be due to'.\n"
        "- ALWAYS populate nutrition_tip for low/moderate risk. For high/critical: nutrition_tip = null.\n"
        "- Use triage-safe language ('may be consistent with', 'could suggest').\n"
        "- If the user asks a general medical question, ANSWER IT directly based on the context.\n"
        "- confidence_score must reflect uncertainty honestly (0.0 - 1.0).\n\n"
        f"{med_instruction}"
        "Return ONLY a valid JSON object with EXACTLY these keys:\n"
        "{\n"
        f"{summary_instruction}\n"
        '  "possible_causes": ["<cause 1>", "<cause 2>", "<cause 3>"],\n'
        f'  "risk_level": "<one of: low | moderate | high | critical>",\n'
        f"{action_instruction}\n"
        f'  "urgency": "<one of: routine | urgent | emergency | critical>",\n'
        '  "confidence_score": <0.0 to 1.0>,\n'
        '  "suggested_otc": "<OTC suggestion string if requested, else null>",\n'
        '  "nutrition_tip": "<1-2 sentence food/hydration tip. Null for high/critical risk.>"\n'
        "}\n\n"
        f"Current assessed risk: {risk_level.upper()}\n"
        f"Current urgency: {urgency.upper()}\n\n"
        f"Patient context:\n{reasoning_input[:1800]}\n\n"
        "JSON response:"
    )

    raw_response = await asyncio.to_thread(call_llama, prompt, max_tokens=max_tokens)

    # FIX #8 — Parse with risk-calibrated max length
    llm_output = _parse_llm_output(raw_response, risk_level, urgency, max_summary_len=max_summary_chars)

    # FIX #8 — Confidence-based response shortening
    conf = llm_output.get("confidence_score", 0.5)
    if conf < 0.6:
        summary = llm_output.get("clinical_summary", "")
        llm_output["clinical_summary"] = (
            summary[:500].rstrip() +
            " This is based on limited information."
        )

    # FIX #4 — Prepend calming prefix if distress detected
    if calming_prefix and llm_output.get("clinical_summary"):
        llm_output["clinical_summary"] = calming_prefix + llm_output["clinical_summary"]

    state["llm_output"] = llm_output

    intent = state.get("intent", "")

    # Store cross-turn context for follow-up turns
    state["last_structured_summary"] = llm_output["clinical_summary"][:600]
    state["last_risk_level"]         = llm_output["risk_level"]
    state["last_intent"]             = intent or "medical_text"

    # Also update upstream risk_level if LLM assessed a different level
    # (allow upgrade only — never downgrade from red_flag assessment)
    _risk_hierarchy = {"unknown": 0, "not_applicable": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
    current_idx = _risk_hierarchy.get(risk_level, 0)
    new_idx = _risk_hierarchy.get(llm_output["risk_level"], 0)

    if new_idx > current_idx:
        state["risk_level"] = llm_output["risk_level"]

    # ── Set trigger_nutrition_node deterministically ─────────────────────────
    # FIX #9 — Only trigger nutrition for moderate/high cases (skip for low)
    _DIET_KEYWORDS = frozenset({"diet", "food", "eat", "meal", "nutrition", "stomach", "nausea",
                                "weight", "sugar", "diabetes", "blood pressure", "cholesterol"})
    search_text = (reasoning_input + " " + " ".join(state.get("symptoms", []))).lower()
    if (
        llm_output["risk_level"] in ("moderate", "high")   # FIX #9: removed "low"
        and any(kw in search_text for kw in _DIET_KEYWORDS)
    ):
        state["trigger_nutrition_node"] = True
    else:
        state["trigger_nutrition_node"] = False

    # Append raw clinical summary to messages for judge validation
    state["messages"] = state.get("messages", []) + [
        {"role": "assistant", "content": llm_output["clinical_summary"]}
    ]

    log_event(logger, "llm_brain_response_generated",
              risk_level=llm_output["risk_level"],
              urgency=llm_output["urgency"],
              confidence=llm_output["confidence_score"])
    return state
