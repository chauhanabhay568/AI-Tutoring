import sqlite3

import database.auth_db as auth_db


def test_register_login_reset_and_update_email_flow(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.db"
    monkeypatch.setattr(auth_db, "DB_PATH", str(db_path))

    auth_db.init_auth_db()

    assert auth_db.register_user("Student@Example.com", "Student", "Password1") == (
        "User registered successfully!"
    )
    assert auth_db.register_user("student@example.com", "Duplicate", "Password1") == (
        "Error: an account with this email already exists."
    )
    assert auth_db.login_user("student@example.com", "wrong") == (
        "Invalid email or password.",
        None,
    )
    assert auth_db.login_user("student@example.com", "Password1") == (
        "Login successful!",
        "Student",
    )

    assert auth_db.reset_password("student@example.com", "Newpass1") == (
        "Password reset successfully!"
    )
    assert auth_db.login_user("student@example.com", "Newpass1") == (
        "Login successful!",
        "Student",
    )

    assert auth_db.update_email("student@example.com", "new@example.com") == (
        "Email updated successfully!"
    )
    assert auth_db.login_user("new@example.com", "Newpass1") == (
        "Login successful!",
        "Student",
    )


def test_register_user_validates_email_and_password(tmp_path, monkeypatch):
    monkeypatch.setattr(auth_db, "DB_PATH", str(tmp_path / "auth.db"))
    auth_db.init_auth_db()

    assert auth_db.register_user("bad-email", "Student", "Password1") == "Invalid email format."
    assert auth_db.register_user("student@example.com", "Student", "short1") == (
        "Password must be at least 8 characters."
    )
    assert auth_db.register_user("student@example.com", "Student", "password") == (
        "Password must contain at least one number."
    )
    assert auth_db.register_user("student@example.com", "Student", "12345678") == (
        "Password must contain at least one letter."
    )


def test_init_auth_db_creates_users_table(tmp_path, monkeypatch):
    db_path = tmp_path / "nested" / "auth.db"
    monkeypatch.setattr(auth_db, "DB_PATH", str(db_path))

    auth_db.init_auth_db()

    with sqlite3.connect(db_path) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone()

    assert table == ("users",)
