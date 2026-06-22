from __future__ import annotations

import logging
import os
import re
import sqlite3

import bcrypt
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

config = dotenv_values()
DB_PATH = config.get("SQLITE_DB_PATH", "database_files/user_data.db")


# ── Private helpers ───────────────────────────────────────────────────────────

def _validate_email(email: str) -> str | None:
    """Return an error string if the email format is invalid, else None."""
    candidate = email.strip().lower()
    if not candidate or candidate.count("@") != 1:
        return "Invalid email format."

    local_part, domain_part = candidate.split("@", 1)
    if not local_part or not domain_part:
        return "Invalid email format."
    if local_part.startswith(".") or local_part.endswith("."):
        return "Invalid email format."
    if domain_part.startswith(".") or domain_part.endswith("."):
        return "Invalid email format."
    if ".." in local_part or ".." in domain_part:
        return "Invalid email format."

    local_pattern = r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+$"
    domain_pattern = r"^(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$"

    if not re.fullmatch(local_pattern, local_part):
        return "Invalid email format."
    if not re.fullmatch(domain_pattern, domain_part):
        return "Invalid email format."
    if any(label.startswith("-") or label.endswith("-") for label in domain_part.split(".")):
        return "Invalid email format."
    return None


def _validate_password(password: str) -> str | None:
    """Return an error string if the password is too weak, else None."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    if not any(c.isalpha() for c in password):
        return "Password must contain at least one letter."
    return None


def _hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if the plain password matches the stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


# ── Database setup ────────────────────────────────────────────────────────────

def init_auth_db() -> None:
    """Create the database folder and users table if they do not already exist."""
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

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

def register_user(email: str, name: str, password: str) -> str:
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
    except sqlite3.Error as exc:
        logger.exception("Failed to register user: %s", exc)
        return "Error registering user."


def login_user(email: str, password: str) -> tuple[str, str | None]:
    """
    Verify credentials.
    Returns ("Login successful!", name) on success,
    or ("Invalid email or password.", None) on failure.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT name, password_hash FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
    except sqlite3.Error as exc:
        logger.exception("Failed to load user for login: %s", exc)
        return ("Invalid email or password.", None)

    if row and _verify_password(password, row[1]):
        return ("Login successful!", row[0])
    return ("Invalid email or password.", None)


def reset_password(email: str, new_password: str) -> str:
    """
    Update the password for a given email.
    Returns a status message.
    """
    password_error = _validate_password(new_password)
    if password_error:
        return password_error

    try:
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
    except sqlite3.Error as exc:
        logger.exception("Failed to reset password: %s", exc)
        return "Error resetting password."

    return "Password reset successfully!"


def update_email(old_email: str, new_email: str) -> str:
    """
    Change a user's email address.
    Returns a status message.
    """
    email_error = _validate_email(new_email)
    if email_error:
        return email_error

    try:
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
    except sqlite3.Error as exc:
        logger.exception("Failed to update email: %s", exc)
        return "Error updating email."
