"""
ocr_processing_node.py  (Version 3 — NEW)
--------------------------------------------
Processes uploaded medical images (prescriptions, lab reports, doctor notes).

Pipeline:
    Image → OCR → Extracted Text → LLaMA → Structured summary.

Anti-hallucination:
    LLaMA only summarizes extracted OCR text. It does NOT diagnose from images.
    Only flags potential concerns and suggests consulting a doctor.
"""

from backend.src.tools.ocr_tool import extract_text_from_image
from backend.src.tools.groq_llama_tool import call_llama
from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("ocr_processing")


def ocr_processing_node(state: TriageState) -> TriageState:
    """
    Extracts text from an uploaded medical image and generates a summary.

    The image path is expected in state["ocr_text"] as a file path (pre-upload).
    After processing, ocr_text is replaced with the structured summary.

    Args:
        state: Contains ocr_text (file path if image mode).

    Returns:
        TriageState: Updated with structured OCR summary.
    """
    image_path = state.get("ocr_text", "")

    # This node only runs for image mode
    if state.get("input_mode") != "image" or not image_path:
        return state

    # ── Step 1: Extract text via OCR ───────────────────────────────────────────
    raw_text = extract_text_from_image(image_path)

    if not raw_text:
        state["ocr_text"] = "Unable to extract text from the uploaded image."
        log_event(logger, "ocr_failed", image_path=image_path)
        return state

    log_event(logger, "ocr_extracted", text_length=len(raw_text))

    # ── Step 2: LLaMA summarization ────────────────────────────────────────────
    prompt = (
        "You are a medical document assistant. Summarize the following extracted text "
        "from a medical document (prescription, lab report, or doctor's note).\n\n"
        "Rules:\n"
        "- DO NOT diagnose.\n"
        "- DO NOT prescribe medication.\n"
        "- Only summarize what the document contains.\n"
        "- Flag any concerning values or notes.\n"
        "- Suggest the patient discuss findings with their doctor.\n\n"
        f"Extracted text:\n{raw_text[:1500]}\n\n"
        "Structured summary:"
    )

    summary = call_llama(prompt, max_tokens=400).strip()

    if not summary:
        summary = f"Extracted text from document:\n{raw_text[:500]}"

    summary += (
        "\n\n⚠️ Disclaimer: This is an automated OCR summary. "
        "Please verify with the original document and consult your healthcare provider."
    )

    state["ocr_text"] = summary

    # Add the OCR summary to the conversation
    state["messages"].append({
        "role": "assistant",
        "content": f"📄 Document Analysis:\n\n{summary}"
    })

    return state
