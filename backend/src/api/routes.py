"""
routes.py  (Version 3)
------------------------
FastAPI endpoints wrapping the LangGraph triage pipeline.

Endpoints:
    POST /triage   — Text-based symptom triage.
    POST /voice    — Voice input (audio file → STT → triage).
    POST /image    — Image upload (prescription/lab report → OCR → summary).
    POST /xray     — X-ray upload (image → vision model → analysis).
    GET  /health   — Health check endpoint.

All endpoints:
    - Validate input with Pydantic models.
    - Return structured JSON responses.
    - Handle errors safely (never expose stack traces).
    - Use async for non-blocking execution.
"""

import os
import re
import uuid
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from backend.src.graph.builder import build_triage_graph
from backend.src.tools.whisper_tool import transcribe_audio
from backend.src.tools.tts_tool import text_to_speech
from backend.src.logging.logger import get_logger, log_event, LatencyTracker

# Allowed file extensions for uploads (security: prevent path traversal)
_ALLOWED_AUDIO_EXT = {".wav", ".mp3", ".webm", ".ogg", ".m4a", ".flac"}
_ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"}


def _sanitize_suffix(filename: str, allowed: set) -> str:
    """Extracts and validates a file extension. Returns '.bin' if invalid."""
    if not filename:
        return ".bin"
    # Strip any path components — only the extension matters
    ext = os.path.splitext(os.path.basename(filename))[1].lower()
    return ext if ext in allowed else ".bin"

logger = get_logger("api")
router = APIRouter()

# Build graph once at module level (reused across requests)
_app = build_triage_graph()


# ── Request/Response models ────────────────────────────────────────────────────

class TriageRequest(BaseModel):
    """Text-based triage request."""
    message: str = Field(..., min_length=1, max_length=2000, description="Patient's symptom description")
    session_id: Optional[str] = Field(None, description="Existing session ID for continuation")
    user_id: Optional[str] = Field("anonymous", description="User identifier")
    language: Optional[str] = Field(None, description="ISO 639-1 language code override")


class TriageResponse(BaseModel):
    """Structured triage response."""
    session_id: str
    response: str
    risk_level: str
    risk_score: float
    risk_confidence: float
    mental_health_flag: bool
    next_action: str
    language: str
    nutrition_advice: Optional[str] = None
    nutrition_image: Optional[str] = None
    judge_passed: bool = True
    audio_url: Optional[str] = None


class VoiceResponse(BaseModel):
    """Voice triage response with transcription."""
    session_id: str
    transcription: str
    detected_language: str
    response: str
    risk_level: str
    risk_score: float
    audio_url: Optional[str] = None


class ImageResponse(BaseModel):
    """OCR/X-ray image analysis response."""
    session_id: str
    analysis: str
    input_mode: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


# ── Helper: Build initial state ───────────────────────────────────────────────

def _build_initial_state(
    message: str,
    input_mode: str = "text",
    session_id: str = "",
    user_id: str = "anonymous",
    language: str = "",
    mid_session: bool = False,
) -> dict:
    """Builds a clean initial state dict for the graph."""
    return {
        "messages": [{"role": "user", "content": message}],
        "symptoms": [],
        "followup_count": 0,
        "retrieved_info": [],
        "risk_score": 0.0,
        "risk_level": "",
        "risk_confidence": 0.0,
        "mental_health_flag": False,
        "next_action": "",
        "_mid_session": mid_session,
        "session_id": session_id,
        "user_id": user_id,
        "language": language,
        "original_input": "",
        "input_mode": input_mode,
        "ocr_text": "",
        "xray_findings": "",
        "nutrition_advice": "",
        "nutrition_image": "",
        "judge_passed": True,
        "judge_feedback": "",
        "audio_url": "",
    }


# ── POST /triage ──────────────────────────────────────────────────────────────

@router.post("/triage", response_model=TriageResponse)
async def triage_endpoint(request: TriageRequest):
    """
    Main text-based triage endpoint.
    Accepts patient symptoms and returns structured risk assessment.
    """
    try:
        with LatencyTracker("triage_request") as tracker:
            has_session = bool(request.session_id)
            state = _build_initial_state(
                message=request.message,
                session_id=request.session_id or "",
                user_id=request.user_id or "anonymous",
                language=request.language or "",
                mid_session=has_session,  # Re-entry: skip load if session exists
            )

            result = await _app.ainvoke(state)

        # Extract the last assistant message as the response
        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        response_text = assistant_msgs[-1]["content"] if assistant_msgs else "Unable to process request."

        log_event(logger, "triage_completed",
                  session_id=result.get("session_id", ""),
                  risk_level=result.get("risk_level", ""),
                  latency_ms=tracker.duration_ms)

        return TriageResponse(
            session_id=result.get("session_id", ""),
            response=response_text,
            risk_level=result.get("risk_level", ""),
            risk_score=result.get("risk_score", 0.0),
            risk_confidence=result.get("risk_confidence", 0.0),
            mental_health_flag=result.get("mental_health_flag", False),
            next_action=result.get("next_action", ""),
            language=result.get("language", "en"),
            nutrition_advice=result.get("nutrition_advice") or None,
            nutrition_image=result.get("nutrition_image") or None,
            judge_passed=result.get("judge_passed", True),
        )

    except Exception as e:
        log_event(logger, "triage_error", error=str(e))
        raise HTTPException(status_code=500, detail="Triage processing failed. Please try again.")


# ── POST /voice ───────────────────────────────────────────────────────────────

@router.post("/voice", response_model=VoiceResponse)
async def voice_endpoint(
    audio: UploadFile = File(...), 
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None)
):
    """
    Voice-based triage endpoint.
    Accepts audio file → Whisper STT → triage → TTS response.
    """
    try:
        # Save uploaded audio to temp file
        suffix = _sanitize_suffix(audio.filename, _ALLOWED_AUDIO_EXT)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        # STT: Audio → Text
        with LatencyTracker("whisper_stt") as stt_tracker:
            stt_result = transcribe_audio(tmp_path)

        transcription = stt_result["text"]
        detected_lang = stt_result["language"]

        if not transcription:
            raise HTTPException(status_code=400, detail="Could not transcribe audio. Please try again.")

        # Run triage pipeline
        with LatencyTracker("voice_triage") as triage_tracker:
            state = _build_initial_state(
                message=transcription,
                input_mode="voice",
                user_id=user_id,
                session_id=session_id or "",
                language=detected_lang,
                mid_session=bool(session_id),
            )
            result = await _app.ainvoke(state)

        # Extract response
        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        response_text = assistant_msgs[-1]["content"] if assistant_msgs else "Unable to process."

        # TTS: Text → Audio
        audio_url = text_to_speech(response_text, language=detected_lang)

        log_event(logger, "voice_triage_completed",
                  stt_latency_ms=stt_tracker.duration_ms,
                  triage_latency_ms=triage_tracker.duration_ms,
                  language=detected_lang)

        # Clean up temp file
        os.unlink(tmp_path)

        return VoiceResponse(
            session_id=result.get("session_id", ""),
            transcription=transcription,
            detected_language=detected_lang,
            response=response_text,
            risk_level=result.get("risk_level", ""),
            risk_score=result.get("risk_score", 0.0),
            audio_url=audio_url or None,
        )

    except HTTPException:
        raise
    except Exception as e:
        log_event(logger, "voice_error", error=str(e))
        raise HTTPException(status_code=500, detail="Voice processing failed. Please try again.")


# ── POST /image ───────────────────────────────────────────────────────────────

@router.post("/image", response_model=ImageResponse)
async def image_endpoint(
    image: UploadFile = File(...), 
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None)
):
    """
    Image-based endpoint for prescriptions, lab reports, doctor notes.
    Runs OCR → LLaMA summarization pipeline.
    """
    try:
        suffix = _sanitize_suffix(image.filename, _ALLOWED_IMAGE_EXT)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await image.read()
            tmp.write(content)
            tmp_path = tmp.name

        with LatencyTracker("image_processing") as tracker:
            state = _build_initial_state(
                message="Uploaded medical document for analysis.",
                input_mode="image",
                user_id=user_id,
                session_id=session_id or "",
                mid_session=bool(session_id),
            )
            # Pass image path through ocr_text field
            state["ocr_text"] = tmp_path

            result = await _app.ainvoke(state)

        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        analysis = assistant_msgs[-1]["content"] if assistant_msgs else "Unable to process image."

        log_event(logger, "image_processed", latency_ms=tracker.duration_ms)

        os.unlink(tmp_path)

        return ImageResponse(
            session_id=result.get("session_id", ""),
            analysis=analysis,
            input_mode="image",
        )

    except Exception as e:
        log_event(logger, "image_error", error=str(e))
        raise HTTPException(status_code=500, detail="Image processing failed. Please try again.")


# ── POST /xray ────────────────────────────────────────────────────────────────

@router.post("/xray", response_model=ImageResponse)
async def xray_endpoint(
    image: UploadFile = File(...), 
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None)
):
    """
    X-ray analysis endpoint.
    Runs vision model classification → LLaMA explanation pipeline.
    """
    try:
        suffix = _sanitize_suffix(image.filename, _ALLOWED_IMAGE_EXT)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await image.read()
            tmp.write(content)
            tmp_path = tmp.name

        with LatencyTracker("xray_processing") as tracker:
            state = _build_initial_state(
                message="Uploaded chest X-ray for analysis.",
                input_mode="xray",
                user_id=user_id,
                session_id=session_id or "",
                mid_session=bool(session_id),
            )
            state["xray_findings"] = tmp_path

            result = await _app.ainvoke(state)

        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        analysis = assistant_msgs[-1]["content"] if assistant_msgs else "Unable to process X-ray."

        log_event(logger, "xray_processed", latency_ms=tracker.duration_ms)

        os.unlink(tmp_path)

        return ImageResponse(
            session_id=result.get("session_id", ""),
            analysis=analysis,
            input_mode="xray",
        )

    except Exception as e:
        log_event(logger, "xray_error", error=str(e))
        raise HTTPException(status_code=500, detail="X-ray processing failed. Please try again.")


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return HealthResponse(status="healthy", version="3.0.0")
