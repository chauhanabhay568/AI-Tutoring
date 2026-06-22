from __future__ import annotations

import certifi
import json
import logging
import os
import sqlite3
from typing import Any

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

config = dotenv_values()
DB_PATH = config.get("SQLITE_STUDENT_DB_PATH", "database_files/student_data.db")


# ── Database setup ────────────────────────────────────────────────────────────

def init_student_db() -> None:
    """Create the database folder and student_profiles table if they do not exist."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_profiles (
                email TEXT PRIMARY KEY,
                data  TEXT NOT NULL
            )
        """)
        conn.commit()
    print("[student_db] Initialised SQLite student store.")


# ── Private helpers ───────────────────────────────────────────────────────────

def _normalise(email: str) -> str:
    return email.strip().lower()


def _row_to_dict(email: str, data_json: str) -> dict[str, Any]:
    data = json.loads(data_json)
    return {"email": email, **data}


def _load_profile(conn: sqlite3.Connection, email: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT data FROM student_profiles WHERE email = ?",
        (email,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_dict(email, row[0])


# ── Public API ────────────────────────────────────────────────────────────────

def save_student_data(data: dict[str, Any]) -> str:
    """Insert a new student profile. Returns a status message string."""
    data = dict(data)
    email = _normalise(data.pop("email", ""))
    if not email:
        return "Error saving data: email is required."
    try:
        payload = json.dumps(data)
    except (TypeError, ValueError) as exc:
        logger.exception("Error serializing data for save: %s", exc)
        return "Error saving data."

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO student_profiles (email, data) VALUES (?, ?)",
                (email, payload),
            )
            conn.commit()
        return "Data saved successfully."
    except sqlite3.IntegrityError:
        return "A profile for this email already exists."
    except sqlite3.Error as exc:
        logger.exception("Error saving data: %s", exc)
        return "Error saving data."


def get_student_by_email(email: str) -> dict[str, Any] | None:
    """Return the student profile dict, or None if not found."""
    email = _normalise(email)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            profile = _load_profile(conn, email)
        return profile
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.exception("Fetch error: %s", exc)
        return None


def student_exists(email: str) -> bool:
    """Return True if a profile exists for this email."""
    email = _normalise(email)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM student_profiles WHERE email = ?", (email,)
            ).fetchone()[0]
        return count > 0
    except sqlite3.Error as exc:
        logger.exception("Exists check failed: %s", exc)
        return False


def update_student_data(email: str, updated_fields: dict[str, Any]) -> str:
    """Merge updated_fields into the existing profile. Returns a status message."""
    email = _normalise(email)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            existing = _load_profile(conn, email)
            if existing is None:
                return "No profile found for this email."
            existing.update(updated_fields)
            payload = json.dumps(existing)
            conn.execute(
                "UPDATE student_profiles SET data = ? WHERE email = ?",
                (payload, email),
            )
            conn.commit()
        return "Data updated successfully."
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.exception("Error updating data: %s", exc)
        return "Error updating data."


def get_all_students() -> list[dict[str, Any]]:
    """Return all student profiles as a list of dicts."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT email, data FROM student_profiles"
            ).fetchall()
        return [_row_to_dict(r[0], r[1]) for r in rows]
    except (sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.exception("Fetch-all error: %s", exc)
        return []


def delete_student(email: str) -> str:
    """Delete a student profile by email. Returns a status message."""
    email = _normalise(email)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute(
                "DELETE FROM student_profiles WHERE email = ?", (email,)
            )
            conn.commit()
        if result.rowcount == 0:
            return "No profile found for this email."
        return "Profile deleted successfully."
    except sqlite3.Error as exc:
        logger.exception("Error deleting profile: %s", exc)
        return "Error deleting profile."


def migrate_from_mongodb(mongodb_uri: str | None = None) -> dict[str, Any]:
    """
    Copy all documents from a MongoDB student collection into SQLite.
    Existing local records are preserved (INSERT OR IGNORE).
    Returns {"migrated": int, "skipped": int, "failed": int, "errors": list[str]}.
    """
    uri = mongodb_uri or config.get("MONGODB_URI", "")
    result: dict[str, Any] = {"migrated": 0, "skipped": 0, "failed": 0, "errors": []}

    if not uri:
        result["errors"].append(
            "MONGODB_URI is not set. Provide it via the mongodb_uri argument or the MONGODB_URI env var."
        )
        return result

    try:
        from pymongo import MongoClient
        from pymongo.errors import PyMongoError
        from pymongo.server_api import ServerApi
    except ImportError as exc:
        logger.exception("MongoDB client import failed: %s", exc)
        result["errors"].append(f"MongoDB import failed: {exc}")
        return result

    try:
        client = MongoClient(
            uri,
            server_api=ServerApi("1"),
            tls=True,
            tlsCAFile=certifi.where(),
        )
        client.admin.command("ping")
        collection = client["ai_tutoring"]["student_data"]
        docs = list(collection.find({}, {"_id": 0}))
    except PyMongoError as exc:
        logger.exception("MongoDB connection failed: %s", exc)
        result["errors"].append(f"MongoDB connection failed: {exc}")
        return result

    with sqlite3.connect(DB_PATH) as conn:
        for doc in docs:
            doc = dict(doc)
            email = _normalise(doc.pop("email", ""))
            if not email:
                result["failed"] += 1
                result["errors"].append("Document missing email field — skipped.")
                continue
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO student_profiles (email, data) VALUES (?, ?)",
                    (email, json.dumps(doc)),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    result["migrated"] += 1
                else:
                    result["skipped"] += 1
            except (sqlite3.Error, TypeError, ValueError, json.JSONDecodeError) as exc:
                result["failed"] += 1
                result["errors"].append(f"{email}: {exc}")
                logger.exception("Migration failed for %s: %s", email, exc)
        conn.commit()

    return result
