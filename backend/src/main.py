"""
main.py  (Version 3)
---------------------
FastAPI application entry point for TriGuard AI Medical Triage System.

Startup:
    uvicorn src.main:app --reload --port 8000

Or via python:
    python -m src.main
"""

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.src.api.routes import router
from backend.src.logging.logger import get_logger, log_event

# Load environment variables relative to this file's parent of parent (backend folder)
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = get_logger("main")

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
)

# ── CORS middleware (allow all origins in dev, restrict in production) ─────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production via env var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routes ───────────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v3", tags=["Triage"])


@app.on_event("startup")
async def startup_event():
    """Runs on application startup."""
    log_event(logger, "app_started",
              version="3.0.0",
              env=os.environ.get("TRIGUARD_ENV", "development"))
    print("\n" + "=" * 60)
    print("  TriGuard AI — Medical Triage System (v3.0.0)")
    print("=" * 60)
    print("  API:    http://localhost:8000/api/v3")
    print("  Docs:   http://localhost:8000/docs")
    print("  Health: http://localhost:8000/api/v3/health")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Runs on application shutdown."""
    log_event(logger, "app_shutdown")


# ── Direct execution ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.src.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
    )
