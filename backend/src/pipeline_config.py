"""
pipeline_config.py  (Version 2 — V5 UPGRADE)
----------------------------------------------
Shared pipeline configuration constants used across multiple nodes.

Centralizing these prevents duplicate definitions and ensures adding a new
input mode or image type requires only a single change.

# 🔥 UPGRADE V5 additions:
    - DOCUMENT_IMAGE_TYPES: image types that route to OCR → text pipeline
    - VISION_ONLY_INTENTS: intents that skip risk scoring (handled by their own nodes)
    - RISK_SKIP_LEVELS: sentinel risk_level values that mean "do not score"
"""

# ── Session persistence config ─────────────────────────────────────────────────
# Input modes that produce no cross-session continuity state.
# These are single-shot analysis requests — no MongoDB load/save required.
# Used by: load_session_node, save_session_node
STATELESS_INPUT_MODES: frozenset = frozenset({"image", "xray", "voice"})

# ── Vision routing config ──────────────────────────────────────────────────────
# 🔥 UPGRADE V5: Image types identified by the vision model that must be
# redirected to the OCR pipeline instead of going to llm_brain.
# Used by: medical_vision_node, vision_classifier_tool
DOCUMENT_IMAGE_TYPES: frozenset = frozenset({
    "document", "report", "prescription", "lab_report", "medical_record",
    "invoice", "letter", "form", "text_document",
})

# 🔥 UPGRADE V5: Intents that bypass risk_evaluation_node scoring.
# These are handled by their own dedicated analysis nodes.
# Used by: risk_evaluation_node
VISION_ONLY_INTENTS: frozenset = frozenset({"xray"})

# 🔥 UPGRADE V5: Sentinel risk_level values set by upstream nodes to signal
# that standard risk scoring should be skipped.
#   "not_applicable" = document image (will re-score after OCR → text pipeline)
#   "unknown"        = vision model failed (cannot safely score)
# Used by: risk_evaluation_node
RISK_SKIP_LEVELS: frozenset = frozenset({"not_applicable", "unknown"})
