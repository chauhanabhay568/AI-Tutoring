import sqlite3
import hashlib

DB_PATH = "database_files/user_data.db"


def init_auth_db():
    """Create the users table if it does not already exist."""
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


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(email, name, password):
    """Insert a new user. Returns a success or error message."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
                (email, name, _hash_password(password)),
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
            "SELECT name, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()

    if row and row[1] == _hash_password(password):
        return ("Login successful!", row[0])
    return ("Invalid email or password.", None)


def reset_password(email, new_password):
    """Update the password for a given email. Returns a status message."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return "Email not found."
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (_hash_password(new_password), email),
        )
        conn.commit()
    return "Password reset successfully!"


def update_email(old_email, new_email):
    """Change a user's email address. Returns a status message."""
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (old_email,)).fetchone()
        if not row:
            return "Current email not found."
        try:
            conn.execute(
                "UPDATE users SET email = ? WHERE email = ?", (new_email, old_email)
            )
            conn.commit()
            return "Email updated successfully!"
        except sqlite3.IntegrityError:
            return "That email address is already in use."
