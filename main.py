import streamlit as st
from time import sleep

from navigation import make_sidebar
from database.auth_db import init_auth_db, register_user, login_user, reset_password, update_email
from utils.css_utils import load_css, load_bootstrap

# ── Initialise database ───────────────────────────────────────────────────────
init_auth_db()

# ── Page setup ────────────────────────────────────────────────────────────────
load_bootstrap()
load_css("styles/style.css")

# FIX 4: Always set on_main_page to True unconditionally.
# Previously used "if not in session_state" which meant navigating
# back to main wouldn't reset it — sidebar could redirect incorrectly.
st.session_state["on_main_page"] = True
make_sidebar()

# FIX 6: Redirect already logged-in users away from the login page.
# If someone is logged in and visits main.py they shouldn't see
# the register/login form again — send them straight to the app.
if st.session_state.get("logged_in"):
    st.switch_page("pages/pre_survey.py")

# ── Content ───────────────────────────────────────────────────────────────────
st.title("Welcome to AI-Assisted Tutoring")
st.write("")

tabs = st.tabs(["Register", "Login", "Reset Password", "Update Email"])

# ── Register ──────────────────────────────────────────────────────────────────
with tabs[0]:
    st.header("Register")
    name     = st.text_input("Name",     key="reg_name",  placeholder="John Doe")
    email    = st.text_input("Email",    key="reg_email", placeholder="example@example.com")
    password = st.text_input("Password", key="reg_pass",  type="password", placeholder="••••••••")

    if st.button("Register", key="reg_btn", use_container_width=True):
        if name and email and password:

            # FIX 5: Basic name validation.
            # Previously someone could register with "1" or "123" as their name.
            if len(name.strip()) < 2:
                st.error("Please enter a valid name (at least 2 characters).")

            else:
                msg = register_user(email, name, password)

                # FIX 1: Only redirect if registration actually succeeded.
                # Previously it always redirected regardless of what
                # register_user() returned — even on validation errors
                # like weak password or invalid email.
                if "successfully" in msg:
                    st.success(msg)
                    st.session_state.update({
                        "logged_in": True,
                        "user_email": email,
                        "user_name": name,
                        "on_main_page": False
                    })
                    sleep(1)
                    st.switch_page("pages/pre_survey.py")
                else:
                    st.error(msg)  # stay on page and show the error

        else:
            st.error("All fields are required.")

# ── Login ─────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.header("Login")
    email    = st.text_input("Email",    key="login_email", placeholder="example@example.com")
    password = st.text_input("Password", key="login_pass",  type="password", placeholder="••••••••")

    if st.button("Login", key="login_btn", use_container_width=True):
        if email and password:
            msg, name = login_user(email, password)
            if "successful" in msg:
                st.success(msg)
                st.session_state.update({
                    "logged_in": True,
                    "user_email": email,
                    "user_name": name,
                    "on_main_page": False
                })
                sleep(1)
                st.switch_page("pages/pre_survey.py")
            else:
                st.error(msg)
        else:
            st.error("Email and password are required.")

# ── Reset Password ────────────────────────────────────────────────────────────
with tabs[2]:
    st.header("Reset Password")
    email        = st.text_input("Email",        key="reset_email", placeholder="example@example.com")
    new_password = st.text_input("New Password", key="reset_pass",  type="password", placeholder="••••••••")

    if st.button("Reset Password", key="reset_btn", use_container_width=True):
        if email and new_password:
            msg = reset_password(email, new_password)

            # FIX 2: Show correct colour based on result.
            # Previously always used st.success() even when the email
            # wasn't found — showed a green box with an error message inside.
            if "successfully" in msg:
                st.success(msg)
            else:
                st.error(msg)
        else:
            st.error("Both fields are required.")

# ── Update Email ──────────────────────────────────────────────────────────────
with tabs[3]:
    st.header("Update Email")
    old_email = st.text_input("Current Email", key="old_email", placeholder="old@example.com")
    new_email = st.text_input("New Email",     key="new_email", placeholder="new@example.com")

    if st.button("Update Email", key="update_btn", use_container_width=True):
        if old_email and new_email:
            msg = update_email(old_email, new_email)

            # FIX 3: Show correct colour based on result.
            # Previously always used st.success() even when the email
            # was already in use or not found.
            if "successfully" in msg:
                st.success(msg)
            else:
                st.error(msg)
        else:
            st.error("Both fields are required.")