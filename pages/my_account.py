import warnings
import streamlit as st
from time import sleep

from navigation import make_sidebar
from database.student_db import init_student_db, save_student_data, update_student_data, get_student_by_email
from utils.css_utils import load_css, load_bootstrap
from utils.chart_utils import (
    student_data_to_dataframe,
    validate_subject_data,
    render_subject_fields,
    render_subject_fields_for_update,
    plot_confidence_bar,
    plot_learning_methods_pie,
    display_learning_goals,
)

warnings.filterwarnings("ignore")

init_student_db()
load_bootstrap()
load_css("styles/style.css")
make_sidebar()

st.title("My Account")

email = st.session_state.get("user_email")

tabs = st.tabs(["View Profile", "Save Profile", "Update Profile"])

# ── View ──────────────────────────────────────────────────────────────────────
with tabs[0]:
    student = get_student_by_email(email)
    if student:
        df = student_data_to_dataframe(student)
        st.header("Preferences Dashboard")

        selected_subject = st.selectbox("Select Subject", df["subject"].unique())
        filtered = df[df["subject"] == selected_subject]

        st.subheader("Confidence & Understanding")
        st.plotly_chart(plot_confidence_bar(filtered))

        st.subheader("Preferred Learning Methods")
        st.plotly_chart(plot_learning_methods_pie(filtered))

        st.subheader("Learning Goals")
        display_learning_goals(filtered)
    else:
        st.info("No profile found. Please save your preferences in the 'Save Profile' tab.")

# ── Save ──────────────────────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Save Preferences")

    with st.form("save_form"):
        age               = st.text_input("Age")
        grade_level       = st.text_input("Grade Level")
        preferred_language = st.text_input("Preferred Language")
        subjects_input    = st.text_input("Subjects (comma-separated)")

        subject_data = {}
        if age and grade_level and preferred_language and subjects_input:
            subjects_list = [s.strip() for s in subjects_input.split(",") if s.strip()]
            subject_data  = render_subject_fields(subjects_list)

        if st.form_submit_button("Save"):
            if not subjects_input:
                st.error("Please enter at least one subject.")
            else:
                error = validate_subject_data(subject_data)
                if error:
                    st.markdown(f"<p style='color:red'>{error}</p>", unsafe_allow_html=True)
                else:
                    result = save_student_data({
                        "email": email,
                        "age": age,
                        "grade_level": grade_level,
                        "preferred_language": preferred_language,
                        "subjects": subjects_input,
                        "subject_details": subject_data,
                    })
                    if "successfully" in result:
                        st.success(result)
                        st.rerun()
                    else:
                        st.error(result)

# ── Update ────────────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Update Preferences")

    student = get_student_by_email(email)
    if not student:
        st.error("No profile found. Please save your preferences first.")
        st.stop()

    with st.form("update_form"):
        updated_subjects = render_subject_fields_for_update(student)

        if st.form_submit_button("Update"):
            result = update_student_data(email, {"subject_details": updated_subjects})
            if "successfully" in result:
                st.success(result)
                sleep(1)
                st.rerun()
            else:
                st.error(result)
