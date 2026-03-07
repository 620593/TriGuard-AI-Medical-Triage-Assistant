"""
async_nutrition_image_node.py  (Version 6)
-------------------------------------------
Fire-and-forget nutrition image generation node.

V6 contract:
    - Runs AFTER response_node in the graph.
    - Checks state["nutrition_image_required"] == True.
    - Sanitizes all LLM-sourced text to prevent prompt injection.
    - Fires image generation as a detached asyncio.create_task.
    - Returns IMMEDIATELY — TTS and persistence nodes are NOT delayed.
    - state["nutrition_image_url"] = "pending" on return (for frontend to poll).
    - On completion, the background task persists the URL to external storage
      (session DB via save_image_url) keyed by session_id.
      The frontend polls GET /image-status?session_id=<id> to retrieve it.
    - No LangGraph state mutation occurs after the node returns
      (no race condition).
    - No LLM calls.

Frontend contract:
    When session_response.nutrition_image_url == "pending", poll:
        GET /api/image-status?session_id=<session_id>
    until a non-"pending" value is returned.

Persistence contract:
    save_image_url(session_id, url) saves to the sessions collection.
    Falls back to log-only if DB is unavailable.
"""

import asyncio
import os
import re

from backend.src.state.state import TriageState
from backend.src.logging.logger import get_logger, log_event

logger = get_logger("async_nutrition_image")

# ── Concurrency controls ──────────────────────────────────────────────────────
_MAX_IMAGE_CONCURRENCY = int(os.getenv("NUTRITION_IMAGE_MAX_CONCURRENCY", "5"))
_IMAGE_GEN_SEMAPHORE   = asyncio.Semaphore(_MAX_IMAGE_CONCURRENCY)

# Timeout for the HuggingFace API call. Tasks that hang beyond this are
# cancelled automatically. Tune via IMAGE_GEN_TIMEOUT_SEC env var.
_IMAGE_GEN_TIMEOUT_SEC = float(os.getenv("IMAGE_GEN_TIMEOUT_SEC", "30"))

# Regular set tracking outstanding tasks.
# Tasks are removed on completion via a done-callback (explicit /deterministic).
# Bounded by the semaphore + timeout: tasks can't accumulate indefinitely.
# On graceful shutdown, call: await drain_pending_image_tasks()
_PENDING_IMAGE_TASKS: set = set()

# ── Prompt injection defence ──────────────────────────────────────────────────
_INJECTION_PATTERN = re.compile(
    r"(ignore previous|forget all|system:|assistant:|as an ai|jailbreak|"
    r"disregard|do not|bypass|unsafe|violent|explicit|nsfw)",
    flags=re.IGNORECASE,
)
_MAX_FIELD_LEN = 120


def _safe(value: str, fallback: str = "general wellness") -> str:
    """Sanitizes an LLM-sourced string before prompt interpolation."""
    if not value or not isinstance(value, str):
        return fallback
    safe = value.replace("\n", " ").replace("\r", "").strip()
    safe = _INJECTION_PATTERN.sub("", safe).strip()
    return safe[:_MAX_FIELD_LEN] or fallback


async def _save_image_url(session_id: str, url: str) -> None:
    """
    Persists the generated image URL to the sessions collection in MongoDB,
    keyed by session_id. This is the out-of-band delivery mechanism for
    background-generated images — no LangGraph state is touched.

    Falls back to log-only if the DB is unavailable.
    """
    try:
        from backend.src.db.mongo_client import get_sessions_collection  # type: ignore
        col = await get_sessions_collection()
        await col.update_one(
            {"session_id": session_id},
            {"$set": {"nutrition_image_url": url}},
            upsert=True,
        )
        log_event(logger, "nutrition_image_url_persisted",
                  session_id=session_id, url=url)
    except Exception as db_exc:
        logger.warning(f"DB persist for image URL failed (log-only fallback): {db_exc}")
        log_event(logger, "nutrition_image_url_log_fallback",
                  session_id=session_id, url=url)


async def drain_pending_image_tasks() -> None:
    """
    Awaits all in-flight nutrition image generation tasks.

    Register this in your FastAPI lifespan shutdown handler:

        from contextlib import asynccontextmanager
        from backend.src.nodes.async_nutrition_image_node import drain_pending_image_tasks

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            await drain_pending_image_tasks()   # drain before process exits

    Ensures MongoDB write for image URLs completes before the server shuts down.
    Harmless if no tasks are pending.
    """
    pending = list(_PENDING_IMAGE_TASKS)
    if pending:
        logger.info(f"Draining {len(pending)} pending image tasks at shutdown...")
        await asyncio.gather(*pending, return_exceptions=True)
        logger.info("All image generation tasks drained.")


# ── Node ──────────────────────────────────────────────────────────────────────

async def async_nutrition_image_node(state: TriageState) -> TriageState:
    """
    Fires nutrition image generation as a detached background task.

    LangGraph state written by this node:
        nutrition_image_url = "pending"   (set before the node returns)

    LangGraph state NOT written by background task:
        The background task does NOT touch the state dict. Instead it persists
        the completed URL to MongoDB, which the frontend polls via API.
        This avoids any post-return state mutation / race condition.

    Args:
        state: Full triage state after response_node has run.

    Returns:
        TriageState with nutrition_image_url = "pending".
    """
    if not state.get("nutrition_image_required", False):
        log_event(logger, "nutrition_image_skipped", reason="flag_not_set")
        return state

    nutrition_out = state.get("nutrition_output", {})
    risk_level    = state.get("risk_level", "low")
    session_id    = state.get("session_id", "unknown")

    # ── Sanitize all LLM-sourced fields ──────────────────────────────────────
    clinical_summary = _safe(
        state.get("llm_output", {}).get("clinical_summary", "")
    )
    rec_foods   = nutrition_out.get("dietary_recommendations", [])
    avoid_foods = nutrition_out.get("foods_to_avoid", [])
    hydration   = nutrition_out.get("hydration_advice", "")

    rec_str       = _safe(", ".join(rec_foods[:4])   if isinstance(rec_foods, list)   else str(rec_foods))
    avoid_str     = _safe(", ".join(avoid_foods[:3]) if isinstance(avoid_foods, list) else str(avoid_foods))
    hydration_str = _safe(str(hydration))

    # ── Build prompt ─────────────────────────────────────────────────────────
    prompt = (
        f"Create a clean, medical-style nutrition guide infographic for: "
        f"{clinical_summary}. "
        f"Include: recommended foods ({rec_str}), "
        f"foods to avoid ({avoid_str}), "
        f"hydration tips ({hydration_str}). "
        f"Clean layout, soft medical colors, minimal text, "
        f"professional but friendly design. "
        f"Do NOT include medical claims. Do NOT include branding."
    )

    # ── Detached background task with timeout ────────────────────────────────
    # Generates the image and persists the URL to MongoDB.
    # Does NOT mutate LangGraph state after this node returns.
    # asyncio.wait_for enforces a hard timeout to prevent hung HF API calls
    # from exhausting semaphore slots indefinitely.
    async def _generate() -> None:
        try:
            from backend.src.tools.nutrition_image_tool import _generate_meal_image
            async with _IMAGE_GEN_SEMAPHORE:
                filename = await asyncio.wait_for(
                    asyncio.to_thread(_generate_meal_image, prompt),
                    timeout=_IMAGE_GEN_TIMEOUT_SEC,
                )
            url = f"/static/nutrition/{filename}" if filename else ""
            await _save_image_url(session_id, url)
        except asyncio.TimeoutError:
            logger.warning(
                f"Nutrition image timed out after {_IMAGE_GEN_TIMEOUT_SEC}s "
                f"(session={session_id})"
            )
            log_event(logger, "nutrition_image_timeout",
                      session_id=session_id, timeout_sec=_IMAGE_GEN_TIMEOUT_SEC)
        except Exception as exc:
            logger.warning(f"Nutrition image generation failed: {exc}")
            log_event(logger, "nutrition_image_failed",
                      session_id=session_id, error=str(exc))

    task = asyncio.create_task(_generate())
    _PENDING_IMAGE_TASKS.add(task)
    # Remove from set immediately on completion (prevents accumulation)
    task.add_done_callback(_PENDING_IMAGE_TASKS.discard)
    log_event(logger, "nutrition_image_task_created", session_id=session_id)

    # ── Set pending flag for frontend polling ─────────────────────────────────
    state["nutrition_image_url"] = "pending"
    return state
