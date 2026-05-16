import os
import re
import sqlite3
import bcrypt
from dotenv import dotenv_values

config = dotenv_values()
DB_PATH = config.get("SQLITE_DB_PATH", "database_files/user_data.db")


# ── Private helpers ───────────────────────────────────────────────────────────

def _validate_email(email):
    """Return an error string if the email format is invalid, else None."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(pattern, email):
        return "Invalid email format."
    return None


def _validate_password(password):
    """Return an error string if the password is too weak, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    if not any(c.isalpha() for c in password):
        return "Password must contain at least one letter."
    return None


def _hash_password(password):
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain_password, hashed_password):
    """Return True if the plain password matches the stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# ── Database setup ────────────────────────────────────────────────────────────

def init_auth_db():
    """Create the database folder and users table if they do not already exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT UNIQUE NOT NULL,
                name          TEXT NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def register_user(email, name, password):
    """
    Validate and insert a new user.
    Returns a success message or a descriptive error string.
    """
    email_error = _validate_email(email)
    if email_error:
        return email_error

    password_error = _validate_password(password)
    if password_error:
        return password_error

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                (email.strip().lower(), name.strip(), _hash_password(password)),
            )
            conn.commit()
        return "User registered successfully!"
    except sqlite3.IntegrityError:
        return "Error: an account with this email already exists."


def login_user(email, password):
    """
    Verify credentials.
    Returns ("Login successful!", name) on success,
    or ("Invalid email or password.", None) on failure.
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT name, password_hash FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    if row and _verify_password(password, row[1]):
        return ("Login successful!", row[0])
    return ("Invalid email or password.", None)


def reset_password(email, new_password):
    """
    Update the password for a given email.
    Returns a status message.
    """
    password_error = _validate_password(new_password)
    if password_error:
        return password_error

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

        if not row:
            return "Email not found."

        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (_hash_password(new_password), email.strip().lower()),
        )
        conn.commit()

    return "Password reset successfully!"


def update_email(old_email, new_email):
    """
    Change a user's email address.
    Returns a status message.
    """
    email_error = _validate_email(new_email)
    if email_error:
        return email_error

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            (old_email.strip().lower(),),
        ).fetchone()

        if not row:
            return "Current email not found."

        try:
            conn.execute(
                "UPDATE users SET email = ? WHERE email = ?",
                (new_email.strip().lower(), old_email.strip().lower()),
            )
            conn.commit()
            return "Email updated successfully!"
        except sqlite3.IntegrityError:
            return "That email address is already in use."