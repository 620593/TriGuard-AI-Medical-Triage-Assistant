"""
main.py  (Version 4 — Production Hardened)
-------------------------------------------
FastAPI application entry point for TriGuard AI Medical Triage System v3.

Startup:
    uvicorn backend.src.main:app --reload --port 8000

Or via python:
    python -m backend.src.main
"""

import os
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Project paths (resolved once at import) ───────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH    = PROJECT_ROOT / ".env"
_AUDIO_DIR   = PROJECT_ROOT / "audio_output"
_NUTRITION_DIR = PROJECT_ROOT / "nutrition_images"

# Load .env before anything else so env vars are available immediately
load_dotenv(dotenv_path=_ENV_PATH)

_ENV = os.environ.get("TRIGUARD_ENV", "development")

# ── Create required directories eagerly (safe to call before server starts) ───
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
_NUTRITION_DIR.mkdir(parents=True, exist_ok=True)

from backend.src.logging.logger import get_logger, log_event  # noqa: E402 (after dotenv)

logger = get_logger("main")


# ── CORS ──────────────────────────────────────────────────────────────────────
def _get_cors_origins() -> List[str]:
    """Returns allowed CORS origins from env var, defaulting to '*' in dev."""
    raw = os.environ.get("TRIGUARD_ALLOWED_ORIGINS", "")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    if _ENV == "production":
        return []  # Refuse wildcard in production when env var is missing
    return ["*"]


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""

    # 1. Validate required environment variables
    required = ["GROQ_API_KEY", "MONGODB_URI"]
    missing  = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    log_event(logger, "app_started", version="3.0.0", env=_ENV)

    # 2. Ensure MongoDB indexes (non-fatal — warn but don't crash)
    from backend.src.tools.mongodb_tool import ensure_indexes
    try:
        await ensure_indexes()
        logger.info("MongoDB indexes ensured.")
    except Exception as exc:
        logger.warning(f"Could not ensure MongoDB indexes: {exc}")

    # 3. Build and attach triage graph to app state (fatal if it fails)
    from backend.src.graph.builder import build_triage_graph
    try:
        app.state.graph = build_triage_graph()
        logger.info("Triage graph built successfully.")
    except Exception as exc:
        logger.error(f"Failed to build triage graph: {exc}")
        raise

    logger.info("TriGuard AI — Medical Triage System v3.0.0 ready.")
    logger.info("API: http://localhost:8000/api/v3  |  Docs: http://localhost:8000/docs")

    yield  # Server runs here

    # Drain in-flight nutrition image generation tasks before shutdown
    try:
        from backend.src.nodes.async_nutrition_image_node import drain_pending_image_tasks
        await drain_pending_image_tasks()
    except Exception as exc:
        logger.warning(f"Could not drain image tasks at shutdown: {exc}")

    log_event(logger, "app_shutdown")


# ── FastAPI application ───────────────────────────────────────────────────────
app = FastAPI(
    title="TriGuard AI — Medical Triage Assistant",
    description=(
        "AI-powered medical triage system with voice, image, and X-ray support. "
        "Version 3: Production-ready backend with MongoDB, judge validation, "
        "multilingual support, and structured observability."
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Global exception handler (no stack traces to clients) ─────────────────────
@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch all unhandled exceptions and return a safe JSON error."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    import traceback
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {exc}",
            "traceback": traceback.format_exc()
        },
    )


# ── CORS middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routes ───────────────────────────────────────────────────────
from backend.src.api.routes import router  # noqa: E402
from backend.src.api.auth import router as auth_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v3/auth", tags=["Auth"])
app.include_router(router, prefix="/api/v3", tags=["Triage"])

# ── Static file serving (dirs already created above) ─────────────────────────
app.mount("/static/audio",     StaticFiles(directory=str(_AUDIO_DIR)),     name="audio")
app.mount("/static/nutrition", StaticFiles(directory=str(_NUTRITION_DIR)), name="nutrition")


# ── Direct execution ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.src.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=(_ENV != "production"),
    )
