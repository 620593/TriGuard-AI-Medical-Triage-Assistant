"""
mongodb_tool.py  (Version 3)
------------------------------
Async MongoDB client for session persistence, user management, and logging.

Connection:
    Default: mongodb://localhost:27017  (local dev)
    Override: set MONGODB_URI env var for Atlas or remote.

Collections:
    - users     : User profiles and preferences.
    - sessions  : Conversation sessions with full state snapshots.
    - reports   : Completed triage reports (immutable after creation).
    - logs      : Pipeline event logs (structured JSON).

Design:
    Uses atomic $set updates (never overwrites full documents).
    All operations return plain dicts (not Mongo cursor objects).
"""

import os
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

# ── Lazy singleton ─────────────────────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_db = None


def _get_db():
    """Returns the MongoDB database instance (lazy singleton)."""
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        _client = AsyncIOMotorClient(uri)
        _db = _client["triguard"]
    return _db


# ── Session operations ────────────────────────────────────────────────────────

async def create_session(user_id: str, initial_state: dict) -> str:
    """
    Creates a new session document and returns its ID as a string.

    Args:
        user_id: User identifier.
        initial_state: Starting state snapshot.

    Returns:
        str: MongoDB ObjectId of the created session.
    """
    db = _get_db()
    doc = {
        "user_id": user_id,
        "state": initial_state,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "status": "active",
    }
    result = await db.sessions.insert_one(doc)
    return str(result.inserted_id)


async def update_session(session_id: str, state_updates: dict) -> bool:
    """
    Atomically updates specific fields in a session document.
    Never overwrites the full document — only $set the changed fields.

    Args:
        session_id: Session ObjectId string.
        state_updates: Dict of state fields to update.

    Returns:
        bool: True if a document was modified.
    """
    from bson import ObjectId
    db = _get_db()
    # Flatten state updates under "state." prefix for atomic $set
    flat = {f"state.{k}": v for k, v in state_updates.items()}
    flat["updated_at"] = datetime.now(timezone.utc)
    result = await db.sessions.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": flat}
    )
    return result.modified_count > 0


async def load_session(session_id: str) -> dict | None:
    """
    Loads a session by ID.

    Returns:
        dict or None: The session document, or None if not found.
    """
    from bson import ObjectId
    db = _get_db()
    doc = await db.sessions.find_one({"_id": ObjectId(session_id)})
    if doc:
        doc["_id"] = str(doc["_id"])   # Serialize ObjectId for JSON compat
    return doc


# ── Report operations ─────────────────────────────────────────────────────────

async def save_report(session_id: str, report_data: dict) -> str:
    """
    Saves a completed triage report (immutable after creation).

    Returns:
        str: Report ObjectId string.
    """
    db = _get_db()
    doc = {
        "session_id": session_id,
        "report": report_data,
        "created_at": datetime.now(timezone.utc),
    }
    result = await db.reports.insert_one(doc)
    return str(result.inserted_id)


# ── Log operations ─────────────────────────────────────────────────────────────

async def insert_log(event: str, data: dict) -> None:
    """
    Inserts a structured log entry into the logs collection.

    Args:
        event: Event name (e.g. 'triage_completed', 'hallucination_detected').
        data: Arbitrary structured data.
    """
    db = _get_db()
    doc = {
        "event": event,
        "data": data,
        "timestamp": datetime.now(timezone.utc),
    }
    await db.logs.insert_one(doc)


# ── User operations ───────────────────────────────────────────────────────────

async def upsert_user(user_id: str, profile: dict) -> None:
    """
    Creates or updates a user profile document.

    Args:
        user_id: User identifier.
        profile: Fields to set (language preference, etc.).
    """
    db = _get_db()
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {**profile, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def get_user(user_id: str) -> dict | None:
    """Fetches a user profile by user_id."""
    db = _get_db()
    doc = await db.users.find_one({"user_id": user_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
