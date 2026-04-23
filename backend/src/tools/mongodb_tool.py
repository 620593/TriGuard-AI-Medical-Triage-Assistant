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
import re
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

# ── ObjectId validation ────────────────────────────────────────────────────────
# MongoDB ObjectId strings are exactly 24 hex characters.
_OBJECT_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _is_valid_object_id(value: str) -> bool:
    """Returns True if value is a properly-formatted MongoDB ObjectId string."""
    return bool(value and _OBJECT_ID_RE.match(value))

import logging

_db_logger = logging.getLogger("triguard.mongodb")

# ── Connection singleton ───────────────────────────────────────────────────────
# Motor's AsyncIOMotorClient MUST be created within the FastAPI event loop
# and NOT recreated in threads or different contexts.
# Initialized ONCE in the FastAPI lifespan via initialize_mongodb().
_client: AsyncIOMotorClient | None = None
_db = None


async def initialize_mongodb():
    """
    Async initializer called ONCE in the FastAPI lifespan.
    Creates the Motor client bound to the FastAPI event loop.

    Must be called before the first request arrives.
    Should be called from the lifespan context manager.
    """
    global _client, _db
    if _client is not None:
        _db_logger.info("Motor client already initialized, skipping.")
        return

    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    _db = _client["triguard"]
    _db_logger.info(f"MongoDB client initialized with URI: mongodb://***")


def _get_db():
    """Returns the MongoDB database instance.

    IMPORTANT: Call initialize_mongodb() in the FastAPI lifespan FIRST.
    This function will raise RuntimeError if Motor client was not initialized.
    """
    global _db
    if _db is None:
        raise RuntimeError(
            "MongoDB client not initialized. "
            "Call initialize_mongodb() in FastAPI lifespan before handling requests."
        )
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

    # Fast-path rejection: validate format before any ObjectId construction
    session_id_str = str(session_id)
    if not _is_valid_object_id(session_id_str):
        return False

    obj_id = ObjectId(session_id_str)

    # Flatten state updates under "state." prefix for atomic $set
    flat = {f"state.{str(k)}": v for k, v in state_updates.items()}
    flat["updated_at"] = datetime.now(timezone.utc)
    result = await db.sessions.update_one(
        {"_id": obj_id},
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

    # Fast-path rejection: validate format before any ObjectId construction
    session_id_str = str(session_id)
    if not _is_valid_object_id(session_id_str):
        return None

    obj_id = ObjectId(session_id_str)
    doc = await db.sessions.find_one({"_id": obj_id})
    if doc:
        doc["_id"] = str(doc["_id"])   # Serialize ObjectId for JSON compat
    return doc


async def load_user_session(session_id: str, user_id: str) -> dict | None:
    """
    Loads a session by ID only if it belongs to the requesting user.

    Returns:
        dict or None: The session document, or None if not found/unauthorized.
    """
    from bson import ObjectId
    db = _get_db()

    session_id_str = str(session_id)
    if not _is_valid_object_id(session_id_str):
        return None

    obj_id = ObjectId(session_id_str)
    doc = await db.sessions.find_one({"_id": obj_id, "user_id": str(user_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── Report operations ─────────────────────────────────────────────────────────

async def save_report(session_id: str, report_data: dict) -> str:
    """
    Saves a completed triage report (immutable after creation).

    Returns:
        str: Report ObjectId string.
    """
    db = _get_db()
    # Validate and coerce session_id to a safe string
    session_id_str = str(session_id) if isinstance(session_id, str) else ""
    doc = {
        "session_id": session_id_str,
        "report": report_data if isinstance(report_data, dict) else {},
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
    # Coerce event to a safe string; reject non-string types silently
    event_str = str(event) if isinstance(event, str) else "unknown_event"
    doc = {
        "event": event_str,
        "data": data if isinstance(data, dict) else {},
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
    safe_user_id = str(user_id)
    await db.users.update_one(
        {"user_id": safe_user_id},
        {"$set": {**profile, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def get_user(user_id: str) -> dict | None:
    """Fetches a user profile by user_id."""
    db = _get_db()
    doc = await db.users.find_one({"user_id": str(user_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_user_by_email(email: str) -> dict | None:
    """Fetches a user profile by email."""
    db = _get_db()
    doc = await db.users.find_one({"email": email})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def create_user(user_data: dict) -> str:
    """Creates a new user profile document."""
    db = _get_db()
    user_data["created_at"] = datetime.now(timezone.utc)
    user_data["updated_at"] = datetime.now(timezone.utc)
    result = await db.users.insert_one(user_data)
    return str(result.inserted_id)


# ── History/Discovery operations ──────────────────────────────────────────────

async def list_user_sessions(user_id: str, limit: int = 20) -> list:
    """Retrieves recent sessions for a specific user."""
    db = _get_db()
    cursor = db.sessions.find({"user_id": str(user_id)}).sort("updated_at", -1).limit(limit)
    sessions = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        sessions.append(doc)
    return sessions


async def list_user_reports(user_id: str, limit: int = 20) -> list:
    """Retrieves recent triage reports for a specific user."""
    db = _get_db()
    cursor = db.reports.find({"report.user_id": str(user_id)}).sort("created_at", -1).limit(limit)
    reports = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        reports.append(doc)
    return reports

async def delete_user_report(report_id: str, user_id: str) -> bool:
    """Deletes a specific triage report if it belongs to the user."""
    from bson import ObjectId
    db = _get_db()
    
    if not _is_valid_object_id(report_id):
        return False
        
    result = await db.reports.delete_one({
        "_id": ObjectId(report_id),
        "report.user_id": str(user_id)
    })
    return result.deleted_count > 0

async def ensure_indexes():
    """Ensure essential indexes exist for performance and uniqueness."""
    db = _get_db()
    
    # Sessions
    await db.sessions.create_index("user_id")
    await db.sessions.create_index("updated_at")
    
    # Reports
    await db.reports.create_index("report.user_id")
    await db.reports.create_index("created_at")
    
    # Users
    await db.users.create_index("user_id", unique=True)
    
    # Logs
    await db.logs.create_index("timestamp")
    await db.logs.create_index("event")
