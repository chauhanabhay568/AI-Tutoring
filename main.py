import streamlit as st
from time import sleep

from navigation import make_sidebar
from database.auth_db import init_auth_db, register_user, login_user, reset_password, update_email
from utils.css_utils import load_css, load_bootstrap

# ── Initialise databases ──────────────────────────────────────────────────────
init_auth_db()

# ── Page setup ────────────────────────────────────────────────────────────────
load_bootstrap()
load_css("styles/style.css")

st.session_state["on_main_page"] = True
make_sidebar()

# ── Content ───────────────────────────────────────────────────────────────────
st.title("Welcome to AI-Assisted Tutoring")
st.write("")

tabs = st.tabs(["Register", "Login", "Reset Password", "Update Email"])

# Register
with tabs[0]:
    st.header("Register")
    name     = st.text_input("Name",     key="reg_name",  placeholder="John Doe")
    email    = st.text_input("Email",    key="reg_email", placeholder="example@example.com")
    password = st.text_input("Password", key="reg_pass",  type="password", placeholder="••••••••")

    if st.button("Register", key="reg_btn", use_container_width=True):
        if name and email and password:
            msg = register_user(email, name, password)
            st.success(msg)
            st.session_state.update({"logged_in": True, "user_email": email,
                                     "user_name": name, "on_main_page": False})
            sleep(1)
            st.switch_page("pages/pre_survey.py")
        else:
            st.error("All fields are required.")

# Login
with tabs[1]:
    st.header("Login")
    email    = st.text_input("Email",    key="login_email", placeholder="example@example.com")
    password = st.text_input("Password", key="login_pass",  type="password", placeholder="••••••••")

    if st.button("Login", key="login_btn", use_container_width=True):
        if email and password:
            msg, name = login_user(email, password)
            if "successful" in msg:
                st.success(msg)
                st.session_state.update({"logged_in": True, "user_email": email,
                                         "user_name": name, "on_main_page": False})
                sleep(1)
                st.switch_page("pages/pre_survey.py")
            else:
                st.error(msg)
        else:
            st.error("Email and password are required.")

# Reset password
with tabs[2]:
    st.header("Reset Password")
    email        = st.text_input("Email",        key="reset_email", placeholder="example@example.com")
    new_password = st.text_input("New Password", key="reset_pass",  type="password", placeholder="••••••••")

    if st.button("Reset Password", key="reset_btn", use_container_width=True):
        if email and new_password:
            st.success(reset_password(email, new_password))
        else:
            st.error("Both fields are required.")

# Update email
with tabs[3]:
    st.header("Update Email")
    old_email = st.text_input("Current Email", key="old_email", placeholder="old@example.com")
    new_email = st.text_input("New Email",     key="new_email", placeholder="new@example.com")

    if st.button("Update Email", key="update_btn", use_container_width=True):
        if old_email and new_email:
            st.success(update_email(old_email, new_email))
        else:
            st.error("Both fields are required.")
