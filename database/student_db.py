import json
import os
import sqlite3

from dotenv import dotenv_values

config = dotenv_values()

DB_PATH = config.get("SQLITE_STUDENT_DB_PATH", "database_files/student_data.db")


# ── Database setup ────────────────────────────────────────────────────────────

def init_student_db():
    """
    Create the student_profiles table if it does not already exist.
    If the database file is missing it is recreated automatically.
    Called once at app startup from pages/my_account.py.
    """
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


# ── Public API ────────────────────────────────────────────────────────────────

def save_student_data(data: dict) -> str:
    """
    Insert a new student profile.
    Email is normalised, pulled out as the primary key, and the rest is
    stored as a JSON blob so the schema can accommodate any survey fields.
    """
    data = dict(data)  # don't mutate caller's dict
    email = data.pop("email", "").strip().lower()
    blob = json.dumps(data)

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO student_profiles (email, data) VALUES (?, ?)",
                (email, blob),
            )
            conn.commit()
        return "Data saved successfully."
    except sqlite3.IntegrityError:
        return "A profile for this email already exists."
    except Exception as e:
        return f"Error saving data: {e}"


def update_student_data(email: str, updated_fields: dict) -> str:
    """
    Merge updated_fields into the existing profile for email.
    Only the supplied keys change; all other stored fields are preserved.
    """
    email = email.strip().lower()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT data FROM student_profiles WHERE email = ?", (email,)
            ).fetchone()

            if row is None:
                return "No profile found for this email."

            existing = json.loads(row[0])
            existing.update(updated_fields)

            conn.execute(
                "UPDATE student_profiles SET data = ? WHERE email = ?",
                (json.dumps(existing), email),
            )
            conn.commit()

        return "Data updated successfully."
    except Exception as e:
        return f"Error updating data: {e}"


def get_student_by_email(email: str) -> dict | None:
    """
    Return a student profile dict (with email injected), or None if not found.
    """
    email = email.strip().lower()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT data FROM student_profiles WHERE email = ?", (email,)
            ).fetchone()

        if row is None:
            return None

        return {"email": email, **json.loads(row[0])}
    except Exception as e:
        print(f"[student_db] fetch error: {e}")
        return None


def get_all_students() -> list:
    """
    Return all student profile dicts. Used by admin for data export.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT email, data FROM student_profiles"
            ).fetchall()
        return [{"email": r[0], **json.loads(r[1])} for r in rows]
    except Exception as e:
        print(f"[student_db] fetch_all error: {e}")
        return []


def student_exists(email: str) -> bool:
    """
    Lightweight check — returns True if a profile exists for this email.
    Does not load the full document.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM student_profiles WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()[0]
        return count > 0
    except Exception:
        return False


def delete_student(email: str) -> str:
    """Delete a student profile by email."""
    email = email.strip().lower()

    try:
        with sqlite3.connect(DB_PATH) as conn:
            result = conn.execute(
                "DELETE FROM student_profiles WHERE email = ?", (email,)
            )
            conn.commit()

        if result.rowcount == 0:
            return "No profile found for this email."
        return "Profile deleted successfully."
    except Exception as e:
        return f"Error deleting profile: {e}"


def migrate_from_mongodb(mongodb_uri: str | None = None) -> dict:
    """
    One-time migration: read all documents from the MongoDB student_data
    collection and insert them into the local SQLite store.

    Uses INSERT OR IGNORE so running this more than once is safe — existing
    local records are never overwritten.

    Returns a summary dict: {migrated, skipped, failed, errors}.
    """
    uri = mongodb_uri or config.get("MONGODB_URI", "")
    result: dict = {"migrated": 0, "skipped": 0, "failed": 0, "errors": []}

    if not uri:
        result["errors"].append("MONGODB_URI not set — cannot connect.")
        return result

    try:
        # Lazy import so the module works without pymongo after migration.
        from pymongo import MongoClient
        from pymongo.server_api import ServerApi
        from pymongo import errors as mongo_errors

        client = MongoClient(
            uri,
            server_api=ServerApi("1"),
            tls=True,
            tlsAllowInvalidCertificates=True,
            serverSelectionTimeoutMS=5000,
        )
        client.admin.command("ping")
        collection = client["ai_tutoring"]["student_data"]
    except Exception as e:
        result["errors"].append(f"MongoDB unreachable: {e}")
        return result

    try:
        with sqlite3.connect(DB_PATH) as conn:
            for doc in collection.find({}, {"_id": 0}):
                doc = dict(doc)
                email = doc.pop("email", "").strip().lower()
                if not email:
                    result["failed"] += 1
                    result["errors"].append("Skipped document with missing email.")
                    continue
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO student_profiles (email, data) VALUES (?, ?)",
                        (email, json.dumps(doc)),
                    )
                    if conn.execute(
                        "SELECT changes()"
                    ).fetchone()[0] > 0:
                        result["migrated"] += 1
                    else:
                        result["skipped"] += 1
                except Exception as e:
                    result["failed"] += 1
                    result["errors"].append(f"Failed for {email}: {e}")
            conn.commit()
    except Exception as e:
        result["errors"].append(f"Migration error: {e}")

    print(
        f"[student_db] Migration complete — "
        f"migrated={result['migrated']}, skipped={result['skipped']}, "
        f"failed={result['failed']}"
    )
    return result
