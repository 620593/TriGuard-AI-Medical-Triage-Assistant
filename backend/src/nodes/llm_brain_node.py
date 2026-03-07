"""
llm_brain_node.py  (Version 6 — FINAL)
-----------------------------------------
Generates a STRICT structured JSON triage response using Groq LLaMA.

V6 contract:
    - Input:  state["reasoning_input"] (from context_synthesizer_node)
    - Output: state["llm_output"] — strict JSON dict:
              {
                "clinical_summary":    str,
                "possible_causes":     [str],
                "risk_level":          str,
                "recommended_action":  str,
                "urgency":             str,
                "confidence_score":    float,
                "suggested_otc":       str or null,
                "nutrition_tip":       str or null
              }
    - No formatting.
    - No presentation.
    - No disclaimers.
    - Reasoning only.
    - Cross-turn context stored in state after success.

V6 fast-exits:
    - vision_error flag → return without calling LLM.
    - empty reasoning_input → return fallback llm_output without calling LLM.
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

    # ── Fast-exit vision logic removed per V6 structural update ───────────────

    # ── Get reasoning input ───────────────────────────────────────────────────
    reasoning_input = (state.get("reasoning_input", "") or "").strip()

    if not reasoning_input:
        state["llm_output"] = _fallback_llm_output(
            "no_reasoning_input", risk_level, urgency
        )
        state["fallback_used"] = True
        msg = empty_input_response(risk_level)
        state["messages"] = state.get("messages", []) + [{"role": "assistant", "content": msg}]
        log_event(logger, "llm_brain_empty_input_exit", risk_level=risk_level)
        return state

    # ── Detect if this is a vision/image analysis case ───────────────────────
    is_vision_case = state.get("intent") == "body_image" and state.get("vision_findings")

    # ── Detect Medication Request ────────────────────────────────────────────
    user_input = state.get("user_input", "").lower()
    med_keywords = ["medicine", "medication", "tablet", "drug", "take for", "suggest medicine", "what should i take", "dolo", "syrup"]
    if any(kw in user_input for kw in med_keywords):
        state["medication_requested"] = True
    else:
        state["medication_requested"] = False

    # ── Build prompt — extended for image analysis cases ─────────────────────
    language = state.get("language", "en")
    lang_instruction = (
        f"Respond in {language} language for the 'clinical_summary' and "
        f"'recommended_action' fields only. All JSON keys must stay in English.\n"
        if language != "en"
        else ""
    )

    if is_vision_case:
        # Vision-specific prompt: ask for comprehensive, detailed explanation
        summary_instruction = (
            '  "clinical_summary": "<Comprehensive 5-7 sentence summary. '
            "Describe: (1) what is visually observed in the image, "
            "(2) the lesion/finding characteristics (color, texture, distribution, size), "
            "(3) what conditions it may be consistent with, "
            "(4) severity assessment, "
            '(5) what the user should watch for>",'
        )
        action_instruction = (
            '  "recommended_action": "<Detailed step-by-step guidance: '
            "when to see a doctor, what to mention at the appointment, "
            "any self-care measures appropriate for the risk level, "
            'and what to avoid doing>",'
        )
        max_tokens   = 700
        max_summary  = 1500
    else:
        summary_instruction = (
            '  "clinical_summary": "<Comprehensive 3-5 sentence plain-language summary. '
            'Directly answer the user\'s question or address their symptoms using the provided medical context. '
            'Be detailed and helpful>",'
        )
        action_instruction = (
            '  "recommended_action": "<Clear, specific next steps or actionable medical advice appropriate for the situation>",'
        )
        max_tokens  = 800
        max_summary = 1000

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

    simple_english_rule = (
        "LANGUAGE RULE — MANDATORY:\n"
        "Write ALL responses in simple, friendly English that a 10-year-old can understand.\n"
        "- Never use medical jargon (replace: pharyngitis \u2192 throat infection, pyrexia \u2192 fever, myalgia \u2192 muscle pain, dyspnea \u2192 difficulty breathing, hypertension \u2192 high blood pressure, tachycardia \u2192 fast heartbeat, edema \u2192 swelling, prognosis \u2192 how things will go, acute \u2192 sudden/severe, chronic \u2192 long-lasting).\n"
        "- Use short sentences. Maximum 15 words per sentence.\n"
        "- Use 'you' and 'your' — talk directly to the patient.\n"
        "- Be warm and reassuring for low/moderate risk; clear and urgent (not scary) for high/critical.\n"
        "- Use simple analogies: 'your body is fighting a germ like a soldier'.\n"
        "- Start clinical_summary with 'It looks like...' or 'It seems like...'\n"
        "- Start recommended_action with 'You should...' or 'Please...'\n"
    )

    prompt = (
        "You are TriGuard AI, a conservative medical triage reasoning engine.\n"
        f"{lang_instruction}"
        f"{simple_english_rule}\n"
        "RULES:\n"
        "- NEVER diagnose or prescribe medications (except as explicitly allowed below).\n"
        "- NEVER invent symptoms not mentioned by the patient or not visible in the image.\n"
        "- ALWAYS populate nutrition_tip for low/moderate risk. For high/critical: nutrition_tip = null.\n"
        "- Use triage-safe language ('may be consistent with', 'could suggest').\n"
        "- If the user asks a general medical question, ANSWER IT directly and thoroughly based on the context.\n"
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
        '  "nutrition_tip": "<1-2 sentence food/hydration tip relevant to symptoms. Null for high/critical risk.>"\n'
        "}\n\n"
        f"Current assessed risk: {risk_level.upper()}\n"
        f"Current urgency: {urgency.upper()}\n\n"
        f"Patient context:\n{reasoning_input[:1800]}\n\n"
        "JSON response:"
    )

    raw_response = await asyncio.to_thread(call_llama, prompt, max_tokens=max_tokens)

    llm_output = _parse_llm_output(raw_response, risk_level, urgency, max_summary_len=max_summary)
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
    _DIET_KEYWORDS = frozenset({"diet", "food", "eat", "meal", "nutrition", "stomach", "nausea", "weight", "sugar", "diabetes", "blood pressure", "cholesterol"})
    search_text = (reasoning_input + " " + " ".join(state.get("symptoms", []))).lower()
    if (
        llm_output["risk_level"] in ("low", "moderate")
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
