from pymongo import MongoClient, errors
from pymongo.server_api import ServerApi
from dotenv import dotenv_values

config = dotenv_values()

_DB_NAME = "ai_tutoring"
_COLLECTION_NAME = "student_data"

_uri = config.get(
    "MONGODB_URI",
    "mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority",
)

_client = MongoClient(_uri, server_api=ServerApi("1"))
_students = _client[_DB_NAME][_COLLECTION_NAME]


def init_student_db():
    """Ensure a unique index on the email field."""
    try:
        _students.create_index("email", unique=True)
    except errors.PyMongoError as e:
        print(f"[student_db] init error: {e}")


def save_student_data(data):
    """Insert a new student document. Returns a status message."""
    try:
        _students.insert_one(data)
        return "Data saved successfully."
    except errors.DuplicateKeyError:
        return "A profile for this email already exists."
    except Exception as e:
        return f"Error saving data: {e}"


def update_student_data(email, updated_fields):
    """Update non-immutable fields for a student. Returns a status message."""
    result = _students.update_one({"email": email}, {"$set": updated_fields})
    if result.matched_count == 0:
        return "No profile found for this email."
    return "Data updated successfully."


def get_student_by_email(email):
    """Return a single student document (without _id), or None."""
    try:
        return _students.find_one({"email": email}, {"_id": 0})
    except Exception as e:
        print(f"[student_db] fetch error: {e}")
        return None


def get_all_students():
    """Return all student documents (without _id)."""
    try:
        return list(_students.find({}, {"_id": 0}))
    except Exception as e:
        print(f"[student_db] fetch_all error: {e}")
        return []
