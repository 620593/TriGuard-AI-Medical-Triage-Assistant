"""
ocr_processing_node.py  (Version 5 — V5 DOCUMENT PIPELINE UPGRADE)
------------------------------------------------------
Processes uploaded medical images (prescriptions, lab reports, doctor notes).

V4 (preserved):
    - Renamed function to ocr_scan_node for naming consistency.
    - Only extracts text via OCR. Does NOT call LLM for summarization.
    - Injects extracted text into state["messages"] as a user message
      so symptom_extraction_node can process it downstream.
    - OCR must run BEFORE symptom extraction. No LLM before extraction.

# 🔥 V5 DOCUMENT PIPELINE UPGRADE:
    1. Sets state["extracted_text"] = cleaned OCR text (canonical field).
    2. Sets state["user_input"]     = OCR text (so llm_brain always has input).
    3. Sets state["ocr_completed"]  = True on successful extraction.
    4. If OCR fails or returns empty:
           state["risk_level"] = "unknown"
           state["ocr_completed"] = False
           state["user_input"] set to safe fallback string.
    5. image_input cleared after OCR to free memory.

Pipeline:
    Image → OCR → Extracted Text → state["messages"] (injected)
                              → state["extracted_text"]
                              → state["user_input"]
                              → state["ocr_completed"] = True

Anti-hallucination:
    No LLM involved. Pure OCR extraction only.
"""

from backend.src.tools.ocr_tool import extract_text_from_image
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event
from backend.src.fallback_responses import ocr_failure_message  # 🔥 V5
import os

logger = get_logger("ocr_scan")

# Allowed file extensions for OCR processing
_ALLOWED_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".pdf"})

# Maximum text lengths (configurable constants, not magic numbers)
MAX_OCR_TEXT_LENGTH = 2000
MAX_MESSAGE_INJECTION_LENGTH = 1500


def _is_safe_image_path(path: str) -> bool:
    """Validates a file path to prevent Local File Inclusion (LFI) attacks."""
    if not path:
        return False
    # Reject directory traversal patterns
    if ".." in path or "~" in path:
        return False
    # Check file extension
    _, ext = os.path.splitext(path)
    return ext.lower() in _ALLOWED_IMAGE_EXTENSIONS


def ocr_scan_node(state: TriageState) -> TriageState:
    """
    Extracts text from an uploaded medical image via OCR.

    # 🔥 V5 DOCUMENT PIPELINE UPGRADE:
    Sets extracted_text, user_input, and ocr_completed in state so that:
      - llm_brain always receives a non-empty user_input (state safety rule)
      - symptom_extraction_node sees the OCR text via state["messages"]
      - risk_evaluation_node can check ocr_completed to confirm pipeline health

    On failure (empty text / exception):
      - state["risk_level"] = "unknown"
      - state["ocr_completed"] = False
      - state["user_input"] = safe fallback message (prevents blank llm_brain call)

    Args:
        state: Contains image_input (raw bytes/b64) or ocr_text (file path).

    Returns:
        TriageState: With extracted text injected into messages and V5 fields set.
    """
    # Try file path first, then raw image data
    image_path = state.get("ocr_text", "")
    image_data = state.get("image_input")

    # ── Guard: Nothing to process ─────────────────────────────────────────────
    if not image_path and not image_data:
        log_event(logger, "ocr_scan_skipped", reason="no_image_data")
        # 🔥 V5 DOCUMENT PIPELINE UPGRADE: set failure state fields
        state["ocr_text"]      = ""
        state["extracted_text"] = ""
        state["user_input"]    = ocr_failure_message()
        state["ocr_completed"] = False
        state["risk_level"]    = "unknown"
        return state

    # ── Guard: File path LFI protection ──────────────────────────────────────
    if image_path and not _is_safe_image_path(image_path):
        log_event(logger, "ocr_scan_rejected", reason="unsafe_file_path")
        state["ocr_text"]      = "Invalid image file path."
        state["extracted_text"] = ""
        state["user_input"]    = ocr_failure_message()
        state["ocr_completed"] = False
        state["risk_level"]    = "unknown"
        return state

    # ── Step 1: Extract text via OCR ──────────────────────────────────────────
    source = image_path if image_path else image_data
    try:
        raw_text = extract_text_from_image(source)
    except Exception as e:
        log_event(logger, "ocr_extraction_failed", error=str(e))
        state["ocr_text"]      = "Unable to extract text from the uploaded image."
        state["extracted_text"] = ""
        state["user_input"]    = ocr_failure_message()
        state["ocr_completed"] = False
        state["risk_level"]    = "unknown"   # 🔥 V5 DOCUMENT PIPELINE UPGRADE
        return state

    # ── Guard: Empty extraction result ────────────────────────────────────────
    if not raw_text or not raw_text.strip():
        log_event(logger, "ocr_empty_result", source=str(type(source).__name__))
        state["ocr_text"]      = "Unable to extract text from the uploaded image."
        state["extracted_text"] = ""
        state["user_input"]    = ocr_failure_message()
        state["ocr_completed"] = False
        state["risk_level"]    = "unknown"   # 🔥 V5 DOCUMENT PIPELINE UPGRADE
        return state

    log_event(logger, "ocr_extracted", text_length=len(raw_text))

    # ── Step 2: Store raw OCR text ────────────────────────────────────────────
    cleaned_text = raw_text.strip()[:MAX_OCR_TEXT_LENGTH]

    state["ocr_text"]      = cleaned_text
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE: set canonical V5 state fields
    state["extracted_text"] = cleaned_text
    state["user_input"]    = cleaned_text   # ensures llm_brain has non-empty input

    # ── Step 3: Inject OCR text into messages for symptom extraction ──────────
    # This allows symptom_extraction_node to process the OCR text
    # as if the user had typed it. Prefix marks it for traceability.
    state["messages"].append({
        "role": "user",
        "content": f"[Medical Document OCR Extract]: {cleaned_text[:MAX_MESSAGE_INJECTION_LENGTH]}"
    })

    # ── Step 4: Mark OCR complete ─────────────────────────────────────────────
    # 🔥 V5 DOCUMENT PIPELINE UPGRADE: downstream nodes check this flag
    state["ocr_completed"] = True

    # ── Step 5: Clear heavy image data from state ─────────────────────────────
    state["image_input"] = None

    return state
