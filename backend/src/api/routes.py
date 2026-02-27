"""
routes.py  (Version 3 - Production-Ready & Secured)
------------------------------------------------------
FastAPI endpoints for TriGuard AI.
Processes images IN-MEMORY only (No Cloudinary).
Safety: Strict User ID validation and secure in-memory buffers.
"""

import os
import re
import tempfile
import uuid
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Header, Request
from pydantic import BaseModel, Field, field_validator
from backend.src.logging.logger import get_logger, log_event, LatencyTracker
from backend.src.tools.mongodb_tool import list_user_sessions, list_user_reports, delete_user_report
from backend.src.tools.whisper_tool import transcribe_audio
from backend.src.tools.tts_tool import text_to_speech
from backend.src.tools.output_parser import parse_response

logger = get_logger("api")
router = APIRouter()

# User ID valid chars
USER_ID_REGEX = r"^[a-zA-Z0-9_\-]+$"

# ── Single authoritative validator ──────────────────────────────────────────

def _validate_uid_string(uid: str) -> bool:
    """Returns True if uid is a non-empty, regex-safe user identifier."""
    return bool(uid and re.match(USER_ID_REGEX, uid))

# ── Dependency ──────────────────────────────────────────────────────────────

async def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Validates User ID from Request Headers, defaults to 'anonymous' if missing."""
    if not x_user_id:
        return "anonymous"
    if not _validate_uid_string(x_user_id):
        raise HTTPException(status_code=400, detail="Invalid User ID format in header")
    return x_user_id

def normalize_user_id(uid: str) -> str:
    """Normalises a User ID: returns 'anonymous' for empty/anonymous values,
    raises 400 for any other value that fails the format check."""
    if not uid or uid == "anonymous":
        return "anonymous"
    if not _validate_uid_string(uid):
        raise HTTPException(status_code=400, detail="Invalid User ID format")
    return uid

# ── Models ──────────────────────────────────────────────────────────────────

class TriageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "anonymous"
    language: Optional[str] = "en"
    use_history: bool = False   # Opt-in: merge past session history into this request

    @field_validator("user_id", mode="before")
    @classmethod
    def check_user_id(cls, v):
        """Delegates to the shared validator to avoid duplicated logic."""
        if not v or v == "anonymous":
            return "anonymous"
        if not _validate_uid_string(v):
            raise ValueError("Invalid User ID format")
        return v

class TriageResponse(BaseModel):
    session_id: str
    response: str                        # Raw full text (always present for fallback)
    risk_level: str
    vision_findings: Optional[dict] = None
    parsed_response: Optional[dict] = None  # Structured sections for rich UI rendering
    nutrition_image: Optional[str] = None   # Filename for HF-generated meal image

class ImageResponse(BaseModel):
    summary: str
    vision_findings: dict
    risk_level: str
    disclaimer: str = "Disclaimer: This is not a diagnosis. Consult a doctor."

# MIME signature bytes for audio validation
_AUDIO_SIGNATURES = [
    b"ID3",                           # MP3 with ID3 tag
    b"\xff\xfb", b"\xff\xf3",         # MP3 raw frames
    b"RIFF",                           # WAV
    b"OggS",                           # OGG
    b"ftyp",                           # M4A (MP4 audio)
    b"\x1aE\xdf\xa3",                 # WebM / MKV
]

def _is_valid_audio_bytes(data: bytes) -> bool:
    """Returns True if data starts with a known audio file signature."""
    if len(data) < 12:
        return False
    for sig in _AUDIO_SIGNATURES:
        if data[:len(sig)] == sig:
            return True
    # WebM 'webm' string appears at offset 8 in some encoders
    return b"webm" in data[:64] or b"OpusHead" in data[:64]

# ── Helper ──────────────────────────────────────────────────────────────────

def _build_initial_state(msg: str, mode: str, sid: str, uid: str, lang: str,
                         use_history: bool = False) -> dict:
    return {
        "messages": [{"role": "user", "content": msg}],
        "symptoms": [],
        "risk_level": "low",
        "risk_score": 0.0,
        "session_id": sid,
        "user_id": uid,
        "language": lang,
        "image_input": None,
        "input_mode": mode,
        "vision_findings": {},
        "next_action": "",
        "judge_passed": True,
        "use_history": use_history,   # Controls history merge in load_history/session nodes
        "judge_feedback": "",
        "audio_url": "",
    }

# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/triage", response_model=TriageResponse)
async def triage_endpoint(request: TriageRequest, req: Request):
    """Main text-based triage endpoint."""
    try:
        state = _build_initial_state(
            request.message,
            "text",
            request.session_id or "",
            request.user_id or "anonymous",
            request.language or "en",
            use_history=request.use_history,  # opt-in history merge
        )
        
        app_graph = req.app.state.graph
        result = await app_graph.ainvoke(state)
        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        raw_response = assistant_msgs[-1]["content"] if assistant_msgs else "No response generated."

        # Parse structured sections for rich frontend rendering
        parsed = parse_response(raw_response)

        return TriageResponse(
            session_id=result.get("session_id", ""),
            response=raw_response,
            risk_level=result.get("risk_level", "low"),
            parsed_response=parsed,
            nutrition_image=result.get("nutrition_image") or None,
        )
    except Exception as e:
        logger.error(f"Triage error: {e}")
        raise HTTPException(status_code=500, detail="Triage engine failure.")

# MIME signature bytes for image validation (no external dependencies)
_IMAGE_SIGNATURES = [
    b"\xff\xd8\xff",       # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"GIF87a", b"GIF89a",  # GIF
    b"RIFF",                # WEBP (checked further below)
    b"BM",                  # BMP
    b"II*\x00", b"MM\x00*",# TIFF
]

def _is_valid_image_bytes(data: bytes) -> bool:
    """Lightweight stdlib-based image MIME check using magic bytes."""
    header = data[:16]
    for sig in _IMAGE_SIGNATURES:
        if header.startswith(sig):
            if sig == b"RIFF":  # WEBP has RIFF header + WEBP marker at byte 8
                return len(data) > 11 and data[8:12] == b"WEBP"
            return True
    return False

@router.post("/image", response_model=ImageResponse)
async def image_endpoint(
    image: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    image_type_hint: Optional[str] = Form(None),  # 'report' | 'prescription' | 'document' | 'body'
    req: Request = None
):
    """Processes medical images IN-MEMORY. Supports body images and medical documents.
    
    The image_type_hint form field controls routing:
      - 'report' | 'prescription' | 'document' | 'lab_report' → OCR pipeline
      - 'body' | None → Medical vision pipeline
    """
    try:
        valid_uid = normalize_user_id(user_id)

        # Security: Limit file size to 10MB
        MAX_SIZE = 10 * 1024 * 1024
        content = await image.read(MAX_SIZE + 1)
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")

        # MIME validation using stdlib magic bytes (no python-magic dependency)
        if not _is_valid_image_bytes(content):
            # Also allow PDF-like documents for OCR (PDF header: %PDF)
            if not content.startswith(b"%PDF"):
                raise HTTPException(status_code=400, detail="Invalid file type. Only images and PDF documents are allowed.")

        # Build initial state — input_mode='image', pass hint for classification
        state = _build_initial_state(
            "Analyze this medical image",
            "image",
            session_id or "",
            valid_uid,
            language or "en"
        )
        state["image_input"] = content
        # Pass the image_type_hint so classification_node can route correctly
        state["image_type_hint"] = (image_type_hint or "").lower()

        with LatencyTracker("vision_request"):
            app_graph = req.app.state.graph
            result = await app_graph.ainvoke(state)

        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        return ImageResponse(
            summary=assistant_msgs[-1]["content"] if assistant_msgs else "Vision analysis complete.",
            vision_findings=result.get("vision_findings", {}),
            risk_level=result.get("risk_level", "low")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image error: {e}")
        raise HTTPException(status_code=500, detail="Image analysis system encountered an error.")


@router.post("/xray", response_model=ImageResponse)
async def xray_endpoint(
    image: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    req: Request = None
):
    """X-Ray analysis endpoint. Always routes through the xray pipeline."""
    try:
        valid_uid = normalize_user_id(user_id)

        MAX_SIZE = 10 * 1024 * 1024
        content = await image.read(MAX_SIZE + 1)
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB.")

        if not _is_valid_image_bytes(content):
            raise HTTPException(status_code=400, detail="Invalid file type. Only images are allowed for X-ray analysis.")

        # Always build state as mode='xray' — never delegates to image_endpoint
        state = _build_initial_state(
            "Analyze this X-ray image",
            "xray",
            session_id or "",
            valid_uid,
            language or "en"
        )
        state["image_input"] = content
        state["image_type_hint"] = "xray"

        with LatencyTracker("xray_request"):
            app_graph = req.app.state.graph
            result = await app_graph.ainvoke(state)

        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        return ImageResponse(
            summary=assistant_msgs[-1]["content"] if assistant_msgs else "X-ray analysis complete.",
            vision_findings=result.get("vision_findings", {}),
            risk_level=result.get("risk_level", "low")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Xray error: {e}")
        raise HTTPException(status_code=500, detail="X-ray analysis system encountered an error.")


class VoiceResponse(BaseModel):
    session_id: str
    transcription: str
    response: str
    risk_level: str
    audio_url: str


@router.post("/voice", response_model=VoiceResponse)
async def voice_endpoint(
    audio: UploadFile = File(...),
    user_id: str = Form("anonymous"),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    req: Request = None
):
    """Voice triage endpoint: transcribes audio and returns triage response."""
    try:
        valid_uid = normalize_user_id(user_id)

        MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
        CHUNK_SIZE     = 65_536            # 64 KB streaming chunks

        suffix    = os.path.splitext(audio.filename or "")[1].lower() or ".webm"
        temp_path = os.path.join(tempfile.gettempdir(), f"audio_{uuid.uuid4().hex}{suffix}")

        import asyncio
        try:
            bytes_written  = 0
            first_chunk    = True
            with open(temp_path, "wb") as fout:
                while True:
                    chunk = await audio.read(CHUNK_SIZE)
                    if not chunk:
                        break

                    # Validate MIME on first chunk only
                    if first_chunk:
                        if not _is_valid_audio_bytes(chunk):
                            raise HTTPException(
                                status_code=400,
                                detail="Invalid file format. Supported: MP3, WAV, OGG, WebM, M4A."
                            )
                        first_chunk = False

                    bytes_written += len(chunk)
                    if bytes_written > MAX_AUDIO_SIZE:
                        raise HTTPException(
                            status_code=413,
                            detail="Audio file too large. Maximum 10 MB."
                        )
                    fout.write(chunk)

            transcription_result = await asyncio.to_thread(transcribe_audio, temp_path)
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

        transcribed_text = transcription_result.get("text", "")
        detected_lang    = transcription_result.get("language") or language or "en"

        if not transcribed_text:
            raise HTTPException(status_code=400, detail="Could not transcribe audio. Please try again.")

        state = _build_initial_state(
            transcribed_text, "voice", session_id or "", valid_uid, detected_lang
        )
        app_graph = req.app.state.graph
        result    = await app_graph.ainvoke(state)

        assistant_msgs = [m for m in result.get("messages", []) if m.get("role") == "assistant"]
        response_text  = assistant_msgs[-1]["content"] if assistant_msgs else "No response generated."

        # Generate TTS audio response
        audio_filename = await asyncio.to_thread(text_to_speech, response_text, detected_lang)

        # Build full static URL using the actual server base URL (portable across environments)
        if audio_filename:
            base = str(req.base_url).rstrip("/")
            audio_url = f"{base}/static/audio/{audio_filename}"
        else:
            audio_url = ""

        return VoiceResponse(
            session_id=result.get("session_id", ""),
            transcription=transcribed_text,
            response=response_text,
            risk_level=result.get("risk_level", "low"),
            audio_url=audio_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice error: {e}")
        raise HTTPException(status_code=500, detail="Voice triage system encountered an error.")

@router.get("/health")
async def health():
    return {"status": "healthy", "version": "3.0.0", "mode": "in-memory-vision"}

@router.get("/sessions")
async def get_sessions(user_id: str = Depends(get_current_user_id)):
    """Lists current user active sessions."""
    return await list_user_sessions(user_id)

@router.get("/reports")
async def get_reports(user_id: str = Depends(get_current_user_id)):
    """Lists current user triage reports."""
    return await list_user_reports(user_id)

@router.delete("/reports/{report_id}")
async def delete_report(report_id: str, user_id: str = Depends(get_current_user_id)):
    """Deletes a specific user triage report."""
    success = await delete_user_report(report_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Report not found or permission denied.")
    return {"status": "success", "message": "Report deleted successfully."}
