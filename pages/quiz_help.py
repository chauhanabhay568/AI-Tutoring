import os
import streamlit as st
import openai
from dotenv import dotenv_values

from navigation import make_sidebar
from database.student_db import get_student_by_email
from utils.css_utils import load_css
from utils.quiz_utils import (
    init_quiz_session_state,
    clear_quiz_session_state,
    load_dummy_quiz,
    generate_quiz,
    parse_quiz_json,
    score_quiz,
    get_quiz_feedback,
)

# ── Config ────────────────────────────────────────────────────────────────────
config = dotenv_values()
openai.api_key = config.get("OPENAI_API_KEY", "")

make_sidebar()
load_css("styles/style.css")
init_quiz_session_state()

dummy_quiz_raw = load_dummy_quiz()

# ── Guard ─────────────────────────────────────────────────────────────────────
email   = st.session_state.get("user_email")
student = get_student_by_email(email)

if not student:
    st.error("Please complete your profile in My Account before using Quiz Help.")
    st.stop()

# ── Preference form ───────────────────────────────────────────────────────────
st.header("Quiz Preferences")
st.write("Fill in the details below to generate a personalised quiz.")

with st.form("quiz_form"):
    st.info("Please fill out all fields.")
    col1, col2, col3 = st.columns(3)

    with col1:
        subject = st.selectbox("Subject", [s.strip() for s in student["subjects"].split(",")])
    with col2:
        topic = st.text_input("Subtopic", placeholder="e.g. Algebra")
    with col3:
        level = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])

    col4, col5, col6 = st.columns([1, 1, 2])
    with col4:
        understanding = st.selectbox("Understanding Level", ["Beginner", "Intermediate", "Advanced"])
    with col5:
        focus = st.radio("Focus", ["Conceptual", "Problem-solving", "Mix of both"])
    with col6:
        num_questions = st.slider("Number of Questions", 5, 20, 10)

    submitted = st.form_submit_button("Generate Quiz")

if submitted:
    st.session_state.update({
        "quiz_form_submitted": True,
        "quiz_subject": subject,
        "quiz_topic": topic,
        "quiz_level": level,
        "quiz_understanding": understanding,
        "quiz_num_questions": num_questions,
        "quiz_focus": focus,
    })
    st.rerun()

# ── Quiz rendering ────────────────────────────────────────────────────────────
ready = (
    st.session_state.quiz_form_submitted
    and not st.session_state.quiz_result_submitted
    and all([
        st.session_state.quiz_subject,
        st.session_state.quiz_topic,
        st.session_state.quiz_level,
        st.session_state.quiz_understanding,
        st.session_state.quiz_num_questions,
        st.session_state.quiz_focus,
    ])
)

if ready:
    placeholder = st.empty()
    placeholder.info("Generating your quiz… please wait.")

    if not st.session_state.quiz_already_generated:
        raw = generate_quiz(
            st.session_state.quiz_subject,
            st.session_state.quiz_topic,
            st.session_state.quiz_level,
            st.session_state.quiz_understanding,
            st.session_state.quiz_num_questions,
            st.session_state.quiz_focus,
        )
        st.session_state.quiz_raw_response = raw
        st.session_state.quiz_already_generated = True
    else:
        raw = st.session_state.quiz_raw_response

    if raw:
        placeholder.empty()
        quiz_data = parse_quiz_json(raw, dummy_quiz_raw)
        st.header("Quiz")

        user_answers = {}
        with st.form("quiz_answers"):
            for idx, q in enumerate(quiz_data):
                st.write(f"**Q{idx + 1}: {q['question']}**")
                if len(q["correct_answers"]) > 1:
                    user_answers[idx] = st.multiselect(
                        f"Select all correct answers for Q{idx + 1}:", q["options"],
                        key=f"q_{idx}",
                    )
                else:
                    user_answers[idx] = st.radio(
                        f"Select the correct answer for Q{idx + 1}:", q["options"],
                        key=f"q_{idx}",
                    )

            if st.form_submit_button("Submit Quiz"):
                st.session_state.quiz_result_submitted = True
                st.session_state.quiz_data         = quiz_data
                st.session_state.quiz_user_answers = user_answers
                st.rerun()

# ── Results ───────────────────────────────────────────────────────────────────
if st.session_state.quiz_result_submitted:
    score, total, display_string = score_quiz(
        st.session_state.quiz_data,
        st.session_state.quiz_user_answers,
    )

    st.header("Quiz Results")
    st.success(f"Your Score: {score}/{total}")

    st.subheader("Solutions")
    st.markdown(
        f"""
        <div style="border:1px solid #ccc; border-radius:8px; padding:16px;
                    background:#f9f9f9; margin-bottom:16px;">
            <pre style="font-size:15px; white-space:pre-wrap;">{display_string}</pre>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Personalised Feedback")
    with st.expander("See recommendations"):
        with st.spinner("Generating feedback…"):
            st.write(get_quiz_feedback(display_string, st.session_state, score / total))

    clear_quiz_session_state()
