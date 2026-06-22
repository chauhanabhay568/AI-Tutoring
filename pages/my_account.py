import warnings
from time import sleep

import streamlit as st

from database.student_db import (
    get_student_by_email,
    init_student_db,
    save_student_data,
    update_student_data,
)
from navigation import make_sidebar
from utils.chart_utils import (
    display_learning_goals,
    plot_confidence_bar,
    plot_learning_methods_pie,
    render_subject_fields,
    render_subject_fields_for_update,
    student_data_to_dataframe,
    validate_subject_data,
)
from utils.css_utils import load_bootstrap, load_css
from utils.subject_management import (
    build_add_subject_updates,
    build_delete_subject_updates,
    build_single_subject_profile,
    build_update_subject_updates,
    canonical_subject_name,
    get_subject_list,
    parse_subjects,
    subject_exists,
)

warnings.filterwarnings("ignore")

init_student_db()
load_bootstrap()
load_css("styles/style.css")
make_sidebar()

st.title("My Account")

email = st.session_state.get("user_email")

tabs = st.tabs(["View Profile", "Save Profile", "Update Profile"])


def _show_result(result: str) -> None:
    if "successfully" in result:
        st.success(result)
        sleep(1)
        st.rerun()
    else:
        st.error(result)


# ── View ──────────────────────────────────────────────────────────────────────

with tabs[0]:
    student = get_student_by_email(email)
    if student:
        df = student_data_to_dataframe(student)
        if df.empty:
            st.info("No subjects found yet. Add your first subject in Save Profile or Update Profile.")
        else:
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
        age = st.text_input("Age")
        grade_level = st.text_input("Grade Level")
        preferred_language = st.text_input("Preferred Language")
        subjects_input = st.text_input("Subjects (comma-separated)")

        subject_data = {}
        if age and grade_level and preferred_language and subjects_input:
            subjects_list = parse_subjects(subjects_input)
            subject_data = render_subject_fields(subjects_list, key_prefix="save_")

        if st.form_submit_button("Save"):
            if not subjects_input:
                st.error("Please enter at least one subject.")
            elif not parse_subjects(subjects_input):
                st.error("Please enter at least one valid subject name.")
            else:
                error = validate_subject_data(subject_data)
                if error:
                    st.markdown(f"<p style='color:red'>{error}</p>", unsafe_allow_html=True)
                else:
                    normalized_subjects = parse_subjects(subjects_input)
                    result = save_student_data(
                        {
                            "email": email,
                            "age": age,
                            "grade_level": grade_level,
                            "preferred_language": preferred_language,
                            "subjects": ", ".join(normalized_subjects),
                            "subject_details": subject_data,
                        }
                    )
                    _show_result(result)


# ── Update ────────────────────────────────────────────────────────────────────

with tabs[2]:
    student = get_student_by_email(email)
    if not student:
        st.error("No profile found. Please save your preferences first.")
    else:
        existing_subjects = get_subject_list(student)

        st.markdown("### Update an Existing Subject")
        if not existing_subjects:
            st.info("No subjects have been saved yet. Add your first subject below.")
        else:
            selected_subject = st.selectbox(
                "Select Subject to Update",
                existing_subjects,
                key="update_existing_subject_select",
            )
            scoped_student = build_single_subject_profile(student, selected_subject)

            with st.form("update_subject_form"):
                updated_subjects = render_subject_fields_for_update(
                    scoped_student,
                    key_prefix="update_existing_",
                )

                if st.form_submit_button("Update Subject"):
                    error = validate_subject_data(updated_subjects)
                    if error:
                        st.markdown(f"<p style='color:red'>{error}</p>", unsafe_allow_html=True)
                    else:
                        try:
                            result_fields = build_update_subject_updates(
                                student,
                                selected_subject,
                                updated_subjects[selected_subject],
                            )
                        except (ValueError, KeyError) as exc:
                            st.error(str(exc))
                        else:
                            result = update_student_data(email, result_fields)
                            _show_result(result)

        st.markdown("### Add a New Subject")
        new_subject_name = st.text_input(
            "Subject Name",
            key="update_new_subject_name",
            placeholder="Enter a new subject",
        )
        clean_new_subject = canonical_subject_name(new_subject_name)

        if clean_new_subject:
            if subject_exists(student, clean_new_subject):
                st.error("A subject with this name already exists.")
            else:
                with st.form("add_subject_form"):
                    subject_details = render_subject_fields(
                        [clean_new_subject],
                        key_prefix="update_add_",
                    )

                    if st.form_submit_button("Add Subject"):
                        error = validate_subject_data(subject_details)
                        if error:
                            st.markdown(f"<p style='color:red'>{error}</p>", unsafe_allow_html=True)
                        else:
                            try:
                                result_fields = build_add_subject_updates(
                                    student,
                                    clean_new_subject,
                                    subject_details[clean_new_subject],
                                )
                            except ValueError as exc:
                                st.error(str(exc))
                            else:
                                result = update_student_data(email, result_fields)
                                _show_result(result)
        else:
            st.info("Enter a subject name above to reveal the subject detail fields.")

        st.markdown("### Delete an Added Subject")
        if not existing_subjects:
            st.info("No subjects are available to delete yet.")
        else:
            with st.form("delete_subject_form"):
                subject_to_delete = st.selectbox(
                    "Select Subject to Delete",
                    existing_subjects,
                    key="delete_subject_select",
                )
                confirm_delete = st.checkbox(
                    "I understand this will remove the selected subject from my profile.",
                    key="delete_subject_confirm",
                )

                if st.form_submit_button("Delete Subject"):
                    if not confirm_delete:
                        st.error("Please confirm the deletion before continuing.")
                    else:
                        try:
                            result_fields = build_delete_subject_updates(student, subject_to_delete)
                        except (ValueError, KeyError) as exc:
                            st.error(str(exc))
                        else:
                            result = update_student_data(email, result_fields)
                            _show_result(result)
