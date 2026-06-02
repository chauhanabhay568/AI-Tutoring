import os
from pymongo import MongoClient, errors
from pymongo.server_api import ServerApi
from dotenv import dotenv_values

config = dotenv_values()

# Private constants — underscore means only used inside this file
_DB_NAME = "ai_tutoring"
_COLLECTION_NAME = "student_data"

# Load URI from 
_uri = config.get("MONGODB_URI", "mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority")

# FIX 1: Lazy connection variables
# Previously the connection was created at import time — if MongoDB was down
# or the URI was wrong, the entire app crashed before showing the login page.
# Now we create the connection only when it is first needed.
_client = None
_students = None


def _get_collection():
    """
    Return the students collection, creating the MongoDB connection
    on first use (lazy initialisation).
    """
    global _client, _students
    if _students is None:
        _client = MongoClient(
                                _uri,
                                server_api=ServerApi("1"),
                                tls=True,
                                tlsAllowInvalidCertificates=True
                            )
        _students = _client[_DB_NAME][_COLLECTION_NAME]
    return _students


# ── Database setup ────────────────────────────────────────────────────────────

def init_student_db():
    """
    Create a unique index on email and verify the connection is reachable.
    Called once at app startup.
    """
    try:
        _get_collection().create_index("email", unique=True)

        # FIX 2: Ping MongoDB to confirm the connection actually works.
        # Without this, a bad URI only causes an error much later when
        # a student tries to save their profile — confusing to debug.
        _client.admin.command("ping")
        print("[student_db] Connected to MongoDB successfully.")
    except errors.PyMongoError as e:
        print(f"[student_db] init error: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

def save_student_data(data):
    """
    Insert a new student document.
    Returns a status message string.
    """
    # FIX 3: Normalise email to lowercase before saving.
    # Without this "Abhay@Gmail.com" and "abhay@gmail.com" would be
    # treated as two different students and create duplicate profiles.
    if "email" in data:
        data["email"] = data["email"].strip().lower()

    try:
        _get_collection().insert_one(data)
        return "Data saved successfully."
    except errors.DuplicateKeyError:
        return "A profile for this email already exists."
    except Exception as e:
        return f"Error saving data: {e}"


def update_student_data(email, updated_fields):
    """
    Update non-immutable fields for a student.
    Returns a status message string.
    """
    # FIX 3: Normalise email so "Abhay@Gmail.com" finds the same
    # profile as "abhay@gmail.com"
    email = email.strip().lower()

    # FIX 4: Added try/except around update.
    # Previously if MongoDB was down during an update the app crashed
    # with an unhandled exception. Now it returns a friendly message.
    try:
        result = _get_collection().update_one(
            {"email": email},
            {"$set": updated_fields}
        )
        if result.matched_count == 0:
            return "No profile found for this email."
        return "Data updated successfully."
    except Exception as e:
        return f"Error updating data: {e}"


def get_student_by_email(email):
    """
    Return a single student document (without _id), or None if not found.
    """
    # FIX 3: Normalise email before querying
    email = email.strip().lower()

    try:
        # {"_id": 0} tells MongoDB not to return the internal _id field
        # because we don't need it and it causes issues with JSON conversion
        return _get_collection().find_one({"email": email}, {"_id": 0})
    except Exception as e:
        print(f"[student_db] fetch error: {e}")
        return None


def get_all_students():
    """
    Return all student documents (without _id) as a list.
    Used by the admin account to download all data.
    """
    try:
        # find({}) means no filter — get everything
        # list() is needed because MongoDB returns a lazy cursor, not a list
        return list(_get_collection().find({}, {"_id": 0}))
    except Exception as e:
        print(f"[student_db] fetch_all error: {e}")
        return []


def student_exists(email):
    """
    FIX 5: Lightweight check — returns True if a profile exists for this email.

    Previously every page called get_student_by_email() just to check existence,
    which fetched the entire document unnecessarily.
    count_documents() with limit=1 stops as soon as it finds one match —
    much faster and uses less memory.
    """
    try:
        return _get_collection().count_documents(
            {"email": email.strip().lower()}, limit=1
        ) > 0
    except Exception:
        return False


def delete_student(email):
    """
    FIX 6: Delete a student profile by email.

    This function was missing entirely. Useful for:
    - Admin cleanup
    - Letting students delete their own account
    - Removing test data during development
    """
    try:
        result = _get_collection().delete_one({"email": email.strip().lower()})
        if result.deleted_count == 0:
            return "No profile found for this email."
        return "Profile deleted successfully."
    except Exception as e:
        return f"Error deleting profile: {e}"